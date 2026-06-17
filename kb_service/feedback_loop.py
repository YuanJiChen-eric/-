"""
第四阶段：反馈闭环演示脚本

模拟课题要求的流程：
  1. 用户提问 → 模型置信度低 → 写入待处理队列（CSV）
  2. 运维人工处理 → 填写标准答案
  3. 自动向量化入库（ChromaDB + BGE-M3）

用法：
  # 模拟一条低置信度记录
  python3 feedback_loop.py add --question "Redis集群脑裂怎么办" --bot-response "无法回答"

  # 查看待处理队列
  python3 feedback_loop.py list

  # 运维处理后入库（本地直连 chroma_store）
  python3 feedback_loop.py resolve --id 1 --resolution "1) 检查哨兵状态..."

  # 通过 HTTP API 入库（kb_service 运行中）
  python3 feedback_loop.py resolve --id 1 --resolution "..." --via-api
"""
import argparse
import csv
import os
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_FILE = os.path.join(BASE_DIR, "kb_service", "data", "pending_tickets.csv")
KB_API = "http://127.0.0.1:8000/api/kb/add"

FIELDNAMES = [
    "id", "question", "bot_response", "status",
    "resolution", "operator_id", "created_at", "resolved_at",
]


def _ensure_queue():
    path = Path(QUEUE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def _read_all() -> list[dict]:
    _ensure_queue()
    with open(QUEUE_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_all(rows: list[dict]):
    with open(QUEUE_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def add_pending(question: str, bot_response: str) -> dict:
    rows = _read_all()
    next_id = max((int(r["id"]) for r in rows), default=0) + 1
    record = {
        "id": str(next_id),
        "question": question,
        "bot_response": bot_response,
        "status": "pending",
        "resolution": "",
        "operator_id": "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "resolved_at": "",
    }
    rows.append(record)
    _write_all(rows)
    print(f"✅ 已加入待处理队列 ID={next_id}")
    return record


def list_pending():
    rows = [r for r in _read_all() if r["status"] == "pending"]
    if not rows:
        print("📭 无待处理记录")
        return
    print(f"📋 待处理 {len(rows)} 条：")
    for r in rows:
        print(f"  [{r['id']}] {r['question'][:60]}")
        print(f"       机器人: {r['bot_response'][:50]}...")


def _sync_to_kb(question: str, answer: str, via_api: bool) -> dict:
    if via_api:
        import requests

        resp = requests.post(
            KB_API,
            json={"question": question, "answer": answer, "skip_if_duplicate": True},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    from chroma_store import store

    return store.add(question=question, answer=answer, dedup=True)


def resolve_ticket(ticket_id: str, resolution: str, operator_id: str = "1", via_api: bool = False) -> dict:
    rows = _read_all()
    target = None
    for r in rows:
        if r["id"] == str(ticket_id):
            target = r
            break
    if not target:
        raise SystemExit(f"❌ 未找到工单 ID={ticket_id}")
    if target["status"] == "resolved":
        raise SystemExit(f"❌ 工单 ID={ticket_id} 已处理")

    kb_result = _sync_to_kb(target["question"], resolution, via_api=via_api)

    target["status"] = "resolved"
    target["resolution"] = resolution
    target["operator_id"] = operator_id
    target["resolved_at"] = datetime.now().isoformat(timespec="seconds")
    _write_all(rows)

    dup = kb_result.get("duplicate", False)
    msg = "跳过（重复）" if dup else "已入库"
    print(f"✅ 工单 {ticket_id} 已处理，知识库{msg}: {kb_result.get('message', kb_result)}")
    return {"ticket": target, "kb": kb_result}


def main():
    parser = argparse.ArgumentParser(description="反馈闭环演示")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="添加待处理记录")
    p_add.add_argument("--question", required=True)
    p_add.add_argument("--bot-response", default="抱歉，我暂时无法处理该问题。")

    sub.add_parser("list", help="列出待处理记录")

    p_resolve = sub.add_parser("resolve", help="处理工单并入库")
    p_resolve.add_argument("--id", required=True)
    p_resolve.add_argument("--resolution", required=True)
    p_resolve.add_argument("--operator-id", default="1")
    p_resolve.add_argument("--via-api", action="store_true", help="通过 HTTP API 入库")

    args = parser.parse_args()

    if args.cmd == "add":
        add_pending(args.question, args.bot_response)
    elif args.cmd == "list":
        list_pending()
    elif args.cmd == "resolve":
        resolve_ticket(args.id, args.resolution, args.operator_id, args.via_api)


if __name__ == "__main__":
    main()
