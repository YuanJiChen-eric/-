"""
将 ops_docs/ 下的运维文档导入 ChromaDB 知识库（通过 HTTP API）
优先使用 ops_docs_clean/（data_clean.py 产出）
"""
import os
import re
import sys
import requests
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPS_DOCS_RAW = os.path.join(BASE_DIR, "ops_docs")
OPS_DOCS_CLEAN = os.path.join(BASE_DIR, "ops_docs_clean")
SKIP_FILES = {"课题要求.md", "运维知识库_sample.md"}

if os.path.isdir(OPS_DOCS_CLEAN) and any(
    f.endswith(".md") for f in os.listdir(OPS_DOCS_CLEAN)
):
    OPS_DOCS_DIR = OPS_DOCS_CLEAN
else:
    OPS_DOCS_DIR = OPS_DOCS_RAW

KB_API = "http://127.0.0.1:8000/api/kb/add"

def parse_markdown(filepath: str) -> list:
    """解析 Markdown 文件，按 ## 标题拆分为 (question, answer) 列表"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(filepath).replace(".md", "")
    
    # 获取文档总标题（第一行 # 标题）
    doc_title = filename
    title_match = re.match(r"^#\s+(.+)", content)
    if title_match:
        doc_title = title_match.group(1).strip()

    # 按 ## 拆分
    sections = re.split(r"\n(?=## )", content)
    
    qa_pairs = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # 提取 ## 标题
        heading_match = re.match(r"^##\s+(.+)", section)
        if not heading_match:
            continue
        heading = heading_match.group(1).strip()
        # 去掉二级标题行，保留内容
        body = re.sub(r"^##\s+.+\n", "", section).strip()
        if not body:
            continue
        
        # 构造问题和答案
        question = f"{doc_title} - {heading}"
        answer = body
        qa_pairs.append((question, answer))
    
    return qa_pairs, doc_title


def import_to_kb(filepath: str):
    """将单个文档导入知识库"""
    qa_pairs, doc_title = parse_markdown(filepath)
    filename = os.path.basename(filepath)
    
    added = 0
    skipped = 0
    
    for question, answer in qa_pairs:
        try:
            resp = requests.post(KB_API, json={
                "question": question,
                "answer": answer,
                "skip_if_duplicate": False,  # 运维文档是全新内容，无需去重
                "dedup_threshold": 0.90
            }, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("duplicate"):
                    skipped += 1
                    print(f"  ⏭️  跳过重复: {question[:60]}... (已有: {data.get('existing_question', '')[:40]}...)")
                else:
                    added += 1
                    print(f"  ✅ 已入库: {question[:60]}...")
            else:
                print(f"  ❌ 请求失败 ({resp.status_code}): {question[:40]}...")
        except Exception as e:
            print(f"  ❌ 异常: {e}")
    
    print(f"\n📄 {filename}: 新增 {added} 条, 跳过 {skipped} 条, 共 {len(qa_pairs)} 个章节")
    return added, skipped


def main():
    if not os.path.exists(OPS_DOCS_DIR):
        print(f"❌ ops_docs 目录不存在: {OPS_DOCS_DIR}")
        sys.exit(1)
    
    # 先检查 kb_service 是否在线
    try:
        resp = requests.get("http://127.0.0.1:8000/api/kb/health", timeout=5)
        if resp.status_code != 200:
            print("❌ kb_service 未就绪")
            sys.exit(1)
        print(f"✅ kb_service 在线，当前知识库: {resp.json().get('records', '?')} 条记录\n")
    except Exception as e:
        print(f"❌ kb_service 连接失败: {e}")
        sys.exit(1)
    
    md_files = sorted([
        f for f in os.listdir(OPS_DOCS_DIR)
        if f.endswith(".md") and f not in SKIP_FILES
    ])
    print(f"📂 文档目录: {OPS_DOCS_DIR}")
    print(f"📂 找到 {len(md_files)} 个文档，开始导入...\n")
    
    total_added = 0
    total_skipped = 0
    
    for md_file in md_files:
        filepath = os.path.join(OPS_DOCS_DIR, md_file)
        added, skipped = import_to_kb(filepath)
        total_added += added
        total_skipped += skipped
    
    print(f"\n{'='*50}")
    print(f"🎉 导入完成！")
    print(f"   新增: {total_added} 条")
    print(f"   跳过(重复): {total_skipped} 条")
    
    # 最终检查
    try:
        resp = requests.get("http://127.0.0.1:8000/api/kb/health", timeout=5)
        print(f"   知识库总计: {resp.json().get('records', '?')} 条记录")
    except:
        pass


if __name__ == "__main__":
    main()
