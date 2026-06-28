"""
第三阶段：Markdown 切片 + 向量化入库

切片策略：
  - 主策略：按 ### 三级标题语义切分（不在句中截断）
  - 辅策略：超长块（>1500 字）用 RecursiveCharacterTextSplitter 二次切分
  - 元数据：source / type / category；date 仅来自 frontmatter（kb_date），不默认填导入日

用法：
  # 追加导入单个文档（服务运行中也可）
  python3 ingest.py --file ../ops_docs_clean/account-management.md

  # 导入整个目录
  python3 ingest.py --dir ../ops_docs_clean

  # 完整重建（等同 rebuild_kb.py）
  python3 ingest.py --rebuild
"""
import argparse
import os
import re
import shutil

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_kb_store")
OPS_DOCS_RAW = os.path.join(BASE_DIR, "ops_docs")
OPS_DOCS_CLEAN = os.path.join(BASE_DIR, "ops_docs_clean")

SKIP_FILES = {"课题要求.md", "运维知识库_sample.md", "README.md"}

# LangChain 二次切分参数（课题建议值）
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
MAX_CHUNK_CHARS = 1500


def resolve_docs_dir() -> str:
    if os.path.isdir(OPS_DOCS_CLEAN) and any(
        f.endswith(".md") for f in os.listdir(OPS_DOCS_CLEAN)
    ):
        return OPS_DOCS_CLEAN
    return OPS_DOCS_RAW


def make_question(doc_name: str, h2_title: str, h3_title: str) -> str:
    clean = re.sub(r"^\d+(\.\d+)*\s*", "", h3_title).strip()
    if re.search(r"(怎么|如何|为什么|是否|能否|什么|哪些|哪个)", clean):
        return f"{doc_name}：{clean}"
    if "现象" in clean or "症状" in clean:
        fact = clean.replace("现象", "").replace("症状", "").strip()
        return f"{doc_name}：{fact}有哪些表现？"
    if "排查" in clean or "步骤" in clean or "速查" in clean:
        fact = clean.replace("排查步骤", "").replace("排查", "").replace("步骤", "").replace("速查", "").strip()
        return f"{doc_name}：怎么排查{fact}？"
    if "解决" in clean or "修复" in clean:
        fact = clean.replace("解决方法", "").replace("解决方案", "").replace("修复方法", "").strip()
        return f"{doc_name}：{fact}怎么解决？"
    if "配置" in clean or "设置" in clean:
        return f"{doc_name}：{clean}怎么配置？"
    if "原因" in clean:
        return f"{doc_name}：{clean}是什么？"
    if "命令" in clean or "指令" in clean:
        return f"{doc_name}：{clean}有哪些？"
    if any(k in clean for k in ("管理", "备份", "恢复", "监控")):
        return f"{doc_name}：{clean}怎么做？"
    return f"{doc_name}：{clean}怎么处理？"


def _split_long_body(body: str) -> list[str]:
    """超长正文二次切分，保留语义边界"""
    if len(body) <= MAX_CHUNK_CHARS:
        return [body]
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "？", "；", "，", " ", ""],
        )
        return splitter.split_text(body)
    except ImportError:
        # 无 LangChain 时按段落粗切
        parts, buf, length = [], [], 0
        for para in body.split("\n\n"):
            if length + len(para) > MAX_CHUNK_CHARS and buf:
                parts.append("\n\n".join(buf))
                buf, length = [para], len(para)
            else:
                buf.append(para)
                length += len(para)
        if buf:
            parts.append("\n\n".join(buf))
        return parts or [body]


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    解析 YAML 风格 frontmatter（测试文档用）
    支持字段：kb_date / kb_version / kb_priority / kb_scenario
    也支持不带 kb_ 前缀的 date / version / priority / scenario
    """
    meta: dict = {}
    body = content
    if not content.startswith("---"):
        return meta, body
    end = content.find("\n---", 3)
    if end == -1:
        return meta, body
    block = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key.startswith("kb_"):
            key = key[3:]
        meta[key] = val
    return meta, body


def _meta_int(meta: dict, key: str, default: int) -> int:
    val = meta.get(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def parse_markdown_file(filepath: str) -> list[dict]:
    """解析 Markdown，返回带元数据的 Q&A 块列表"""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    file_meta, content = _parse_frontmatter(raw)
    filename = os.path.basename(filepath)
    doc_name = filename.replace(".md", "")
    title_match = re.match(r"^#\s+(.+)", content)
    if title_match:
        doc_name = title_match.group(1).strip()

    source_id = filename.replace(".md", "")
    scenario = file_meta.get("scenario", source_id)
    chunks: list[dict] = []

    sections = re.split(r"\n(?=## )", content)
    for section in sections:
        h2_match = re.match(r"^##\s+(.+)", section)
        if not h2_match:
            continue
        h2_title = h2_match.group(1).strip()
        subsections = re.split(r"\n(?=### )", section)

        for sub in subsections:
            sub = sub.strip()
            if not sub:
                continue
            h3_match = re.match(r"^###\s+(.+)", sub)
            if h3_match:
                h3_title = h3_match.group(1).strip()
                body = re.sub(r"^###\s+.+\n", "", sub).strip()
                question = make_question(doc_name, h2_title, h3_title)
            else:
                body = re.sub(r"^##\s+.+\n", "", sub).strip()
                if not body or len(body) < 20:
                    continue
                question = f"{doc_name}：{h2_title}怎么处理？"

            if not body or len(body) < 20:
                continue

            for i, part in enumerate(_split_long_body(body)):
                q = question if i == 0 else f"{question}（第{i + 1}部分）"
                chunk_meta = {
                    "source": source_id,
                    "type": "ops_doc",
                    "category": h2_title,
                    "doc_title": doc_name,
                    "source_file": filename,
                    "priority": _meta_int(file_meta, "priority", 100),
                    "version": _meta_int(file_meta, "version", 1),
                    "test_scenario": scenario,
                }
                # 仅 frontmatter 显式标注时才写入 date；勿用导入当天冒充文档修订日
                if file_meta.get("date"):
                    chunk_meta["date"] = file_meta["date"]
                chunks.append({
                    "question": q,
                    "answer": part,
                    "metadata": chunk_meta,
                })
    return chunks


def ingest_file(filepath: str, store, dedup: bool = False, handle_conflicts: bool = True) -> dict:
    pairs = parse_markdown_file(filepath)
    result = store.batch_add(
        pairs,
        dedup=dedup,
        handle_conflicts=handle_conflicts,
    )
    result["file"] = os.path.basename(filepath)
    result["chunks"] = len(pairs)
    return result


def ingest_directory(docs_dir: str, store, dedup: bool = False, handle_conflicts: bool = True) -> dict:
    total_added = 0
    total_skipped = 0
    files = sorted(
        f for f in os.listdir(docs_dir)
        if f.endswith(".md") and f not in SKIP_FILES
    )
    for name in files:
        r = ingest_file(os.path.join(docs_dir, name), store, dedup=dedup, handle_conflicts=handle_conflicts)
        total_added += r["added"]
        total_skipped += r["skipped"]
        print(f"  ✓ {name}: {r['added']} 块")
    return {"added": total_added, "skipped": total_skipped, "files": len(files)}


def rebuild_full(store) -> int:
    """完整重建：种子 FAQ + 运维文档"""
    from seed_data import SEED_DATA, expand_to_500

    print("  导入种子 FAQ ...")
    store.batch_add(SEED_DATA)
    if store.count() < 500:
        store.batch_add(expand_to_500())
    print(f"  种子数据: {store.count()} 条")

    docs_dir = resolve_docs_dir()
    print(f"  导入文档: {docs_dir}")
    r = ingest_directory(docs_dir, store, dedup=False)
    print(f"  文档块: +{r['added']} 条")
    return store.count()


def main():
    parser = argparse.ArgumentParser(description="运维知识库切片入库")
    parser.add_argument("--file", help="导入单个 Markdown 文件")
    parser.add_argument("--dir", help="导入目录下所有 Markdown")
    parser.add_argument("--rebuild", action="store_true", help="清空并完整重建")
    parser.add_argument("--dedup", action="store_true", help="开启语义去重")
    args = parser.parse_args()

    if args.rebuild:
        if os.path.isdir(CHROMA_PATH):
            shutil.rmtree(CHROMA_PATH)
            print(f"[ingest] 已删除旧库: {CHROMA_PATH}")

    from chroma_store import store

    if args.rebuild:
        print("=" * 60)
        print("  完整重建知识库")
        print("=" * 60)
        total = rebuild_full(store)
        print(f"\n✅ 重建完成，共 {total} 条")
        return 0

    if args.file:
        r = ingest_file(args.file, store, dedup=args.dedup)
        print(f"✅ {r['file']}: 新增 {r['added']} 条, 跳过 {r['skipped']} 条")
        return 0

    if args.dir:
        print(f"📂 导入目录: {args.dir}")
        r = ingest_directory(args.dir, store, dedup=args.dedup)
        print(f"✅ 完成: 新增 {r['added']} 条, 跳过 {r['skipped']} 条")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
