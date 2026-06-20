"""
运维文档数据清洗脚本（第二阶段）

功能：
  - 去噪：删除控制字符、多余空格与空行
  - 结构化：统一标题层级与列表格式
  - 实体保护：URL、命令、HTTP 状态码、IP 不被破坏

用法：
  python3 data_clean.py                    # 默认 ops_docs → ops_docs_clean
  python3 data_clean.py --input ../ops_docs --output ../ops_docs_clean
  python3 data_clean.py --dry-run          # 仅预览变更统计
"""
import argparse
import os
import re
import unicodedata
from pathlib import Path

# 非知识库文档，清洗时跳过
SKIP_FILES = {"课题要求.md"}

# 需保护的实体模式（清洗时标记占位，最后再还原）
PLACEHOLDER_PREFIX = "⟦ENT"
PLACEHOLDER_SUFFIX = "⟧"

ENTITY_PATTERNS = [
    # URL（含课题示例 http://XXX.YYY.ZZZ）
    (r"https?://[^\s\)>\"']+", "URL"),
    # systemctl / docker / mysql 等命令行
    (r"(?:systemctl|docker|mysql|nginx|redis-cli|journalctl|curl|ping|telnet|nc|grep|kill|lsof|df|ipconfig|ifconfig)\s+[^\n]{3,120}", "CMD"),
    # HTTP 状态码 / Error 码
    (r"(?:Error\s+\d{3}|HTTP\s+\d{3}|\b[45]\d{2}\s+(?:Bad Gateway|Internal|Unauthorized|Forbidden|Timeout)[^\n]*)", "ERR"),
    # IP 地址
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP"),
    # JDBC / API 路径
    (r"jdbc:mysql://[^\s\"']+", "JDBC"),
    (r"/api/[a-z_/]+", "API"),
]


def _protect_entities(text: str) -> tuple[str, list[str]]:
    """将实体替换为占位符，避免清洗破坏"""
    entities: list[str] = []
    protected = text

    for pattern, _kind in ENTITY_PATTERNS:
        def repl(m, kind=_kind):
            idx = len(entities)
            entities.append(m.group(0))
            return f"{PLACEHOLDER_PREFIX}{kind}{idx}{PLACEHOLDER_SUFFIX}"

        protected = re.sub(pattern, repl, protected, flags=re.IGNORECASE)

    return protected, entities


def _restore_entities(text: str, entities: list[str]) -> str:
    def repl(m):
        idx = int(m.group(2))
        if 0 <= idx < len(entities):
            return entities[idx]
        return m.group(0)

    return re.sub(
        rf"{PLACEHOLDER_PREFIX}(\w+)(\d+){PLACEHOLDER_SUFFIX}",
        repl,
        text,
    )


def remove_noise(text: str) -> str:
    """删除控制字符、统一换行、压缩空白"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 删除除 \n \t 外的控制字符
    cleaned = []
    for ch in text:
        if ch in ("\n", "\t"):
            cleaned.append(ch)
        elif unicodedata.category(ch) != "Cc":
            cleaned.append(ch)
    text = "".join(cleaned)
    # 行尾空格
    text = re.sub(r"[ \t]+\n", "\n", text)
    # 行内连续空格（保留代码块内）
    lines = text.split("\n")
    result_lines = []
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            result_lines.append(line)
            continue
        if in_code:
            result_lines.append(line)
        else:
            result_lines.append(re.sub(r"[^\S\n]{2,}", " ", line.rstrip()))
    text = "\n".join(result_lines)
    # 最多连续 2 个空行
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip() + "\n"


def normalize_headings(text: str) -> str:
    """确保标题前有空行，层级格式统一"""
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        if re.match(r"^#{1,6}\s+", line):
            if out and out[-1].strip() != "":
                out.append("")
            line = re.sub(r"^(#{1,6})\s*", lambda m: m.group(1) + " ", line)
            line = re.sub(r"\s+$", "", line)
        out.append(line)
    return "\n".join(out)


def normalize_lists(text: str) -> str:
    """统一列表符号为 - """
    lines = text.split("\n")
    out = []
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if not in_code:
            m = re.match(r"^(\s*)[•·▪]\s+", line)
            if m:
                line = f"{m.group(1)}- " + line[m.end():]
            m = re.match(r"^(\s*)\d+\.\s+", line)
            if m and not line.strip().startswith("#"):
                # 保留有序列表数字
                pass
        out.append(line)
    return "\n".join(out)


def clean_markdown(content: str) -> str:
    protected, entities = _protect_entities(content)
    protected = remove_noise(protected)
    protected = normalize_headings(protected)
    protected = normalize_lists(protected)
    return _restore_entities(protected, entities)


def clean_file(src: Path, dst: Path, dry_run: bool = False) -> dict:
    raw = src.read_text(encoding="utf-8")
    cleaned = clean_markdown(raw)
    changed = raw != cleaned
    stats = {
        "file": src.name,
        "changed": changed,
        "chars_before": len(raw),
        "chars_after": len(cleaned),
    }
    if not dry_run and changed:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(cleaned, encoding="utf-8")
    elif not dry_run and not changed:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(cleaned, encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser(description="运维 Markdown 文档清洗")
    default_input = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops_docs"
    )
    default_output = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops_docs_clean"
    )
    parser.add_argument("--input", default=default_input, help="原始文档目录")
    parser.add_argument("--output", default=default_output, help="清洗后输出目录")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不写文件")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.is_dir():
        print(f"❌ 输入目录不存在: {input_dir}")
        return 1

    md_files = sorted(
        f for f in input_dir.glob("*.md") if f.name not in SKIP_FILES
    )
    print(f"📂 清洗目录: {input_dir}")
    print(f"📤 输出目录: {output_dir}")
    print(f"📄 文件数量: {len(md_files)}")
    if args.dry_run:
        print("🔍 模式: dry-run（不写文件）\n")

    changed_count = 0
    for src in md_files:
        dst = output_dir / src.name
        stats = clean_file(src, dst, dry_run=args.dry_run)
        flag = "✏️ " if stats["changed"] else "✓ "
        print(
            f"  {flag}{stats['file']}: "
            f"{stats['chars_before']} → {stats['chars_after']} chars"
        )
        if stats["changed"]:
            changed_count += 1

    print(f"\n{'=' * 50}")
    print(f"  完成: {len(md_files)} 个文件, {changed_count} 个有变更")
    if not args.dry_run:
        print(f"  清洗结果: {output_dir}")
        print(f"  下一步: python3 rebuild_kb.py  （将自动使用 ops_docs_clean）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
