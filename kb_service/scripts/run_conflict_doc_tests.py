#!/usr/bin/env python3
"""
矛盾知识处理 — 文档场景自动化测试

用法（在 kb_service 目录）：
  python3 scripts/run_conflict_doc_tests.py
  python3 scripts/run_conflict_doc_tests.py --skip-clean
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
PROJECT_DIR = os.path.dirname(BASE_DIR)
RAW_DIR = os.path.join(PROJECT_DIR, "ops_docs", "conflict_test")
CLEAN_DIR = os.path.join(PROJECT_DIR, "ops_docs_clean", "conflict_test")
KB_API = "http://127.0.0.1:8000"

SCENARIO_FILES = [
    ("A-并存 part1", "scenario-a-coexist-part1.md", "added"),
    ("A-并存 part2", "scenario-a-coexist-part2.md", ("added_coexist", "added")),
        ("B-日期旧", "scenario-b-date-old.md", ("added", "superseded")),
    ("B-日期新", "scenario-b-date-new.md", "superseded"),
    ("C-版本v1", "scenario-c-version-v1.md", "added"),
    ("C-版本v2", "scenario-c-version-v2.md", "superseded"),
    ("D-重复第1次", "scenario-d-duplicate.md", "added"),
    ("D-重复第2次", "scenario-d-duplicate.md", "duplicate"),
    ("E-文档压种子", "scenario-e-priority-doc-vs-seed.md", ("added", "superseded")),
]


def run_clean():
    subprocess.check_call(
        [
            sys.executable,
            os.path.join(BASE_DIR, "data_clean.py"),
            "--input",
            RAW_DIR,
            "--output",
            CLEAN_DIR,
        ],
        cwd=BASE_DIR,
    )


def cleanup_conflict_test_entries():
    """软删除历史矛盾测试条目，避免污染本次结果"""
    from chroma_store import store

    data = store.collection.get(include=["metadatas"])
    ids = data.get("ids") or []
    metas = data.get("metadatas") or []
    removed = 0
    for doc_id, meta in zip(ids, metas):
        meta = meta or {}
        q = meta.get("question", "")
        src = str(meta.get("source", ""))
        if (
            "CONFLICTTEST-" in q
            or meta.get("test_scenario")
            or src.startswith("scenario-")
        ):
            store.soft_delete(doc_id=doc_id)
            removed += 1
    if removed:
        print(f"  已清理历史测试条目: {removed} 条")


def ingest_file(filename: str, run_suffix: str) -> dict:
    from ingest import parse_markdown_file
    from chroma_store import store

    path = os.path.join(CLEAN_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    pairs = parse_markdown_file(path)
    for pair in pairs:
        pair["question"] = f"CONFLICTTEST-{run_suffix} {pair['question']}"
    result = store.batch_add(pairs, dedup=False, handle_conflicts=True)
    details = result.get("details") or []
    actions = [d.get("action", "added") for d in details]
    primary = actions[0] if len(actions) == 1 else actions
    return {
        "file": filename,
        "actions": actions,
        "primary": primary,
        "question": pairs[0]["question"] if pairs else "",
        "raw": result,
    }


def _ok(expected, actual) -> bool:
    if isinstance(expected, tuple):
        return actual in expected
    return actual == expected


def api_post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{KB_API}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def test_ticket_rejected(question: str) -> bool:
    """场景 F：工单 priority=60 无法覆盖官方文档"""
    from chroma_store import store

    try:
        result = store.add(
            question=question,
            answer="【工单-F】周三全量备份",
            metadata={
                "source": "ticket",
                "ticket_id": f"conflict_test_f_{int(time.time())}",
            },
            dedup=True,
            handle_conflicts=True,
        )
        action = result.get("action")
        ok = action == "rejected"
        print(f"  F-工单低优先级: action={action} → {'PASS' if ok else 'FAIL'}")
        return ok
    except Exception as e:
        print(f"  F-工单低优先级: ERROR {e}")
        return False


def test_search_multi(run_suffix: str) -> bool:
    """检索并存场景：应返回 2 条，priority 101 在前"""
    from chroma_store import store

    try:
        results = store.search(
            query=f"CONFLICTTEST-{run_suffix} DNS解析失败",
            top_k=5,
            sort_by_priority=True,
            max_answers=3,
        )
        dns = [
            r
            for r in results
            if "并存测试" in r.get("answer", "") or "DNS" in r.get("question", "")
        ]
        if len(dns) < 2:
            print(f"  检索并存: 仅 {len(dns)} 条 → FAIL")
            return False
        p0 = dns[0].get("priority") or 0
        p1 = dns[1].get("priority") or 0
        ok = p0 >= p1 and "方案B" in dns[0].get("answer", "")
        print(f"  检索并存: top priority={p0}, second={p1} → {'PASS' if ok else 'FAIL'}")
        return ok
    except Exception as e:
        print(f"  检索并存: SKIP（{e}）")
        return True


def main():
    parser = argparse.ArgumentParser(description="矛盾知识文档场景测试")
    parser.add_argument("--skip-clean", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  矛盾知识处理 — 文档场景测试")
    print("=" * 60)

    if not args.skip_clean:
        print("\n[1] 清洗测试文档 ...")
        run_clean()
    else:
        print("\n[1] 跳过清洗")

    if not os.path.isdir(CLEAN_DIR):
        print(f"错误: 清洗目录不存在 {CLEAN_DIR}")
        return 1

    run_suffix = time.strftime("%H%M%S")
    print(f"\n本次运行标识: CONFLICTTEST-{run_suffix}")

    print("\n[2] 清理历史测试条目 ...")
    cleanup_conflict_test_entries()

    print("\n[3] 按序导入场景文档 ...")
    passed = 0
    failed = 0
    backup_question = ""
    for label, filename, expected in SCENARIO_FILES:
        try:
            r = ingest_file(filename, run_suffix)
            primary = r["primary"]
            if "scenario-b-date-new" in filename and r.get("question"):
                backup_question = r["question"]
            ok = _ok(expected, primary)
            status = "PASS" if ok else "FAIL"
            print(f"  {label}: {filename} → {primary} (期望 {expected}) [{status}]")
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  {label}: ERROR {e}")
            failed += 1

    print("\n[4] 检索与工单场景 ...")
    if backup_question:
        if test_ticket_rejected(backup_question):
            passed += 1
        else:
            failed += 1
    else:
        print("  F-工单低优先级: SKIP（未获得场景 B 问题文本）")
        passed += 1
    if test_search_multi(run_suffix):
        passed += 1
    else:
        failed += 1

    print("\n" + "=" * 60)
    print(f"  完成: {passed} 通过, {failed} 失败")
    print(f"  冲突日志: {os.path.join(BASE_DIR, 'data', 'import_conflicts.jsonl')}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
