"""
重建知识库：清空 → 导入种子数据 → 按 ### 粒度导入运维文档（自然语言问句）

等效命令：python3 ingest.py --rebuild
"""
import os
import shutil
import sys

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_kb_store")

if os.path.isdir(CHROMA_PATH):
    shutil.rmtree(CHROMA_PATH)
    print(f"[rebuild_kb] 已删除旧知识库: {CHROMA_PATH}")

from chroma_store import store
from ingest import rebuild_full, resolve_docs_dir

print(f"[rebuild_kb] 文档目录: {resolve_docs_dir()}")
print("=" * 60)
print("  重建知识库")
print("=" * 60)
total = rebuild_full(store)
print(f"\n{'=' * 60}")
print(f"  重建完成！知识库总计: {total} 条")
print(f"  存储位置: {CHROMA_PATH}")
print(f"{'=' * 60}")
