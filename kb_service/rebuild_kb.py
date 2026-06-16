"""
重建知识库：清空 → 导入种子数据 → 按 ### 粒度导入运维文档（自然语言问句）
"""
import os
import re
import sys

# 设置 HuggingFace 镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from chroma_store import store
from seed_data import SEED_DATA, expand_to_500

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPS_DOCS_RAW = os.path.join(BASE_DIR, "ops_docs")
OPS_DOCS_CLEAN = os.path.join(BASE_DIR, "ops_docs_clean")

# 优先使用清洗后的文档（data_clean.py 产出）
if os.path.isdir(OPS_DOCS_CLEAN) and any(
    f.endswith(".md") for f in os.listdir(OPS_DOCS_CLEAN)
):
    OPS_DOCS_DIR = OPS_DOCS_CLEAN
    print(f"[rebuild_kb] 使用清洗后文档: {OPS_DOCS_DIR}")
else:
    OPS_DOCS_DIR = OPS_DOCS_RAW
    print(f"[rebuild_kb] 使用原始文档: {OPS_DOCS_DIR}")

# 非知识库内容，导入时跳过
SKIP_FILES = {
    "课题要求.md",           # 课题说明文档，非运维知识
}


def make_question(doc_name: str, h2_title: str, h3_title: str) -> str:
    """
    把 ### 标题转成自然语言问句，始终以文档名开头确保搜索匹配
    例如:
      doc_name="Nginx 运维排错手册", h3_title="1.1 端口被占用"
      → "Nginx：端口被占用怎么排查？"
      doc_name="Docker 运维实战手册", h3_title="1.1 常用命令速查"
      → "Docker：常用命令速查有哪些？"
    """
    # 去掉编号前缀（如 "1.1 "、"2.3.1 "）
    clean = re.sub(r"^\d+(\.\d+)*\s*", "", h3_title).strip()

    # 已经有"怎么"/"如何"/"为什么"等词，直接拼接
    if re.search(r"(怎么|如何|为什么|是否|能否|什么|哪些|哪个)", clean):
        return f"{doc_name}：{clean}"

    # 根据关键词构造问句
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
    if "管理" in clean or "备份" in clean or "恢复" in clean or "监控" in clean:
        return f"{doc_name}：{clean}怎么做？"

    # 默认：前置文档名
    return f"{doc_name}：{clean}怎么处理？"


# ── 步骤 1：清空知识库 ──
print("=" * 60)
print("  步骤 1/3：清空现有知识库")
print("=" * 60)
store.clear()
print(f"  当前记录数: {store.count()}")

# ── 步骤 2：重新导入种子数据 ──
print(f"\n{'=' * 60}")
print("  步骤 2/3：导入种子 FAQ 数据")
print("=" * 60)
store.batch_add(SEED_DATA)
base = store.count()
print(f"  基础数据: {base} 条")
if base < 500:
    expanded = expand_to_500()
    store.batch_add(expanded)
    print(f"  扩充: +{len(expanded)} 条")
print(f"  当前总计: {store.count()} 条")


# ── 步骤 3：按 ### 切片导入运维文档 ──
print(f"\n{'=' * 60}")
print("  步骤 3/3：导入运维文档（### 切片 + 自然语言问句）")
print("=" * 60)


def parse_ops_docs(filepath: str):
    """
    按 ### 标题切分 Markdown
    返回 [(question: str, answer: str), ...]
    question 是自然语言问句，不是目录路径
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    doc_name = os.path.basename(filepath).replace(".md", "")
    title_match = re.match(r"^#\s+(.+)", content)
    if title_match:
        doc_name = title_match.group(1).strip()

    qa_pairs = []

    # 按 ## 拆分大章节
    sections = re.split(r"\n(?=## )", content)

    for section in sections:
        h2_match = re.match(r"^##\s+(.+)", section)
        if not h2_match:
            continue
        h2_title = h2_match.group(1).strip()

        # 再按 ### 拆分子节
        subsections = re.split(r"\n(?=### )", section)

        for sub in subsections:
            sub = sub.strip()
            if not sub:
                continue

            h3_match = re.match(r"^###\s+(.+)", sub)
            if h3_match:
                # 有 ### 子标题 → 生成自然语言问句
                h3_title = h3_match.group(1).strip()
                body = re.sub(r"^###\s+.+\n", "", sub).strip()
                question = make_question(doc_name, h2_title, h3_title)
            else:
                # 没有 ###，整个 ## 节作为一块
                body = re.sub(r"^##\s+.+\n", "", sub).strip()
                if not body or len(body) < 20:
                    continue
                question = f"{doc_name}：{h2_title}怎么处理？"

            if body and len(body) > 20:
                qa_pairs.append((question, body))

    return qa_pairs, doc_name


md_files = sorted([
    f for f in os.listdir(OPS_DOCS_DIR)
    if f.endswith(".md") and f not in SKIP_FILES
])
total_chunks = 0

for md_file in md_files:
    filepath = os.path.join(OPS_DOCS_DIR, md_file)
    qa_pairs, doc_name = parse_ops_docs(filepath)

    result = store.batch_add(
        [{"question": q, "answer": a} for q, a in qa_pairs],
        dedup=False
    )

    total_chunks += result["added"]
    print(f"  ✓ {md_file}: {result['added']} 块")

print(f"\n{'=' * 60}")
print(f"  重建完成！")
print(f"  运维文档块数: {total_chunks}")
print(f"  知识库总计: {store.count()} 条")
print(f"  存储位置: {os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'chroma_kb_store')}")
print(f"{'=' * 60}")
