"""
导入时矛盾知识检测与优先级仲裁（纯逻辑，无向量库依赖）

策略：
  - 问题相似 + 答案相同 → duplicate
  - 问题相似 + 答案矛盾：
      1. priority 不同 → 高者 supersede
      2. priority 相同 + 双方都有 date → 新日期 supersede 旧日期
      3. priority 相同 + 双方都有 version → 高版本 supersede 低版本
      4. 无法依 date/version 裁决 → coexist（双条保留，新条 priority +1）
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

CONFLICT_SIMILARITY_THRESHOLD = 0.80
DEFAULT_DEDUP_THRESHOLD = 0.90
MAX_ANSWERS_PER_QUERY = 3

SOURCE_PRIORITY: dict[str, int] = {
    "ops_doc": 100,
    "manual": 80,
    "expanded": 80,
    "seed": 80,
    "ticket": 60,
    "conflict_test": 10,
}

TYPE_PRIORITY: dict[str, int] = {
    "ops_doc": 100,
}

DEFAULT_PRIORITY = 50

DATE_KEYS = ("date", "revision_date", "updated_at", "doc_date")

DATA_DIR = Path(__file__).resolve().parent / "data"
CONFLICT_LOG = DATA_DIR / "import_conflicts.jsonl"


def normalize_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def answer_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:16]


def answers_equivalent(a: str, b: str) -> bool:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return na == nb
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 40 and shorter in longer:
        if len(shorter) / max(len(longer), 1) >= 0.85:
            return True
    return False


def get_priority(metadata: dict | None) -> int:
    if not metadata:
        return DEFAULT_PRIORITY
    if metadata.get("priority") is not None:
        try:
            return int(metadata["priority"])
        except (TypeError, ValueError):
            pass
    doc_type = metadata.get("type")
    if doc_type and doc_type in TYPE_PRIORITY:
        return TYPE_PRIORITY[doc_type]
    source = str(metadata.get("source", ""))
    return SOURCE_PRIORITY.get(source, DEFAULT_PRIORITY)


def parse_date(metadata: dict | None) -> datetime | None:
    if not metadata:
        return None
    for key in DATE_KEYS:
        val = metadata.get(key)
        if val is None or val == "":
            continue
        text = str(val).strip()
        if not text:
            continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d")
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(text.replace("Z", "")[:19])
        except ValueError:
            continue
    return None


def parse_version(metadata: dict | None) -> int | None:
    if not metadata or metadata.get("version") is None:
        return None
    try:
        return int(metadata["version"])
    except (TypeError, ValueError):
        return None


def both_have_dates(new_meta: dict | None, existing_meta: dict | None) -> bool:
    return parse_date(new_meta) is not None and parse_date(existing_meta) is not None


def both_have_versions(new_meta: dict | None, existing_meta: dict | None) -> bool:
    return parse_version(new_meta) is not None and parse_version(existing_meta) is not None


def questions_equivalent(a: str, b: str) -> bool:
    return normalize_text(a) == normalize_text(b)


def effective_similarity_score(
    question: str,
    existing_question: str,
    vector_score: float,
    conflict_threshold: float = CONFLICT_SIMILARITY_THRESHOLD,
) -> float:
    if questions_equivalent(question, existing_question):
        return max(vector_score, conflict_threshold)
    return vector_score


def resolve_conflict_action(new_meta: dict | None, existing_meta: dict | None) -> str:
    """
    返回: supersede | reject | coexist
    """
    new_p = get_priority(new_meta)
    existing_p = get_priority(existing_meta)
    if new_p > existing_p:
        return "supersede"
    if new_p < existing_p:
        return "reject"

    # 同优先级：日期 → 版本 → 并存
    if both_have_dates(new_meta, existing_meta):
        new_date = parse_date(new_meta)
        old_date = parse_date(existing_meta)
        if new_date and old_date:
            if new_date > old_date:
                return "supersede"
            if new_date < old_date:
                return "reject"

    if both_have_versions(new_meta, existing_meta):
        new_ver = parse_version(new_meta)
        old_ver = parse_version(existing_meta)
        if new_ver is not None and old_ver is not None:
            if new_ver > old_ver:
                return "supersede"
            if new_ver < old_ver:
                return "reject"

    return "coexist"


def coexist_priority_boost(new_meta: dict | None, existing_meta: dict | None) -> int:
    """并存时抬高新条 priority，保证回答时排序靠前"""
    return max(get_priority(new_meta), get_priority(existing_meta)) + 1


def search_result_sort_key(item: dict) -> tuple:
    """检索结果排序：priority ↓, version ↓, date ↓, score ↓"""
    meta = item.get("metadata") or {}
    p = get_priority(meta)
    v = parse_version(meta) or 0
    d = parse_date(meta)
    d_ord = d.timestamp() if d else 0.0
    return (-p, -v, -d_ord, -float(item.get("score", 0)))


def sort_search_results(results: list[dict]) -> list[dict]:
    return sorted(results, key=search_result_sort_key)


def plan_import_action(
    new_answer: str,
    new_metadata: dict | None,
    existing_id: str,
    existing_answer: str,
    existing_metadata: dict | None,
    similarity_score: float,
    handle_conflicts: bool = True,
    dedup_only: bool = False,
    conflict_threshold: float = CONFLICT_SIMILARITY_THRESHOLD,
    dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
) -> dict:
    threshold = conflict_threshold if handle_conflicts else dedup_threshold
    if similarity_score < threshold:
        return {"action": "add", "conflict": False, "score": similarity_score}

    if answers_equivalent(new_answer, existing_answer):
        return {
            "action": "duplicate",
            "conflict": False,
            "existing_id": existing_id,
            "score": similarity_score,
            "message": (
                f"已存在实质相同答案 (相似度={similarity_score:.2%}, ID={existing_id})，跳过"
            ),
        }

    if not handle_conflicts and dedup_only:
        return {
            "action": "duplicate",
            "conflict": False,
            "existing_id": existing_id,
            "score": similarity_score,
            "message": (
                f"已存在相似记录 (相似度={similarity_score:.2%}, ID={existing_id})，跳过新增"
            ),
        }

    if not handle_conflicts:
        return {"action": "add", "conflict": False, "score": similarity_score}

    conflict_action = resolve_conflict_action(new_metadata, existing_metadata)
    if conflict_action == "supersede":
        reason = _supersede_reason(new_metadata, existing_metadata)
        return {
            "action": "supersede",
            "conflict": True,
            "existing_id": existing_id,
            "score": similarity_score,
            "message": (
                f"检测到矛盾知识，{reason}，将覆盖 ID={existing_id}"
                f" (相似度={similarity_score:.2%})"
            ),
        }

    if conflict_action == "coexist":
        boosted = coexist_priority_boost(new_metadata, existing_metadata)
        return {
            "action": "coexist",
            "conflict": True,
            "existing_id": existing_id,
            "score": similarity_score,
            "boosted_priority": boosted,
            "message": (
                f"无法依日期/版本裁决，与 ID={existing_id} 并存"
                f" (新 priority={boosted}, 相似度={similarity_score:.2%})"
            ),
        }

    return {
        "action": "rejected",
        "conflict": True,
        "existing_id": existing_id,
        "score": similarity_score,
        "message": (
            f"检测到矛盾知识，已有记录更优，保留 ID={existing_id}"
            f" (相似度={similarity_score:.2%})"
        ),
    }


def _supersede_reason(new_meta: dict | None, existing_meta: dict | None) -> str:
    new_p = get_priority(new_meta)
    old_p = get_priority(existing_meta)
    if new_p > old_p:
        return "新来源优先级更高"
    if both_have_dates(new_meta, existing_meta):
        return "新记录日期更新"
    if both_have_versions(new_meta, existing_meta):
        return "新记录版本更高"
    return "新记录更优"


def log_import_conflict(
    question: str,
    new_answer: str,
    new_metadata: dict | None,
    existing_id: str,
    existing_answer: str,
    existing_metadata: dict | None,
    similarity_score: float,
    action: str,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "similarity": round(similarity_score, 4),
        "question": question[:500],
        "new_answer_preview": new_answer[:300],
        "existing_id": existing_id,
        "existing_answer_preview": existing_answer[:300],
        "new_priority": get_priority(new_metadata),
        "existing_priority": get_priority(existing_metadata),
        "new_date": str(parse_date(new_metadata) or ""),
        "existing_date": str(parse_date(existing_metadata) or ""),
        "new_version": parse_version(new_metadata),
        "existing_version": parse_version(existing_metadata),
        "new_metadata": new_metadata or {},
        "existing_metadata": existing_metadata or {},
    }
    with open(CONFLICT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
