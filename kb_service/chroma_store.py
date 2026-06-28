"""
ChromaDB 向量知识库封装
使用 BGE-M3 Embedding（中文语义检索优化）
持久化目录：项目根目录 chroma_kb_store/（与成员 A 的 chroma_db/ 隔离）
"""
import os
import shutil

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from kb_conflict import (
    CONFLICT_SIMILARITY_THRESHOLD,
    DEFAULT_DEDUP_THRESHOLD,
    MAX_ANSWERS_PER_QUERY,
    effective_similarity_score,
    get_priority,
    log_import_conflict,
    parse_date,
    parse_version,
    plan_import_action,
    sort_search_results,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_kb_store")
COLLECTION_NAME = "ops_knowledge"

EMBEDDING_MODEL_LOCAL = os.path.join(BASE_DIR, "local_models", "BAAI", "bge-m3")
EMBEDDING_MODEL_HF = "BAAI/bge-m3"


def _find_local_model() -> str | None:
    """扫描 local_models 目录，找到可用的 BGE-M3"""
    if os.path.isdir(EMBEDDING_MODEL_LOCAL):
        for root, _, files in os.walk(EMBEDDING_MODEL_LOCAL):
            if "config.json" in files and (
                "pytorch_model.bin" in files or "model.safetensors" in files
            ):
                return root
    bge_root = os.path.join(BASE_DIR, "local_models", "BAAI")
    if os.path.isdir(bge_root):
        for name in sorted(os.listdir(bge_root)):
            candidate = os.path.join(bge_root, name)
            if os.path.isdir(candidate):
                for root, _, files in os.walk(candidate):
                    if "config.json" in files and (
                        "pytorch_model.bin" in files or "model.safetensors" in files
                    ):
                        return root
    return None


def _resolve_model_name() -> str:
    local = _find_local_model()
    if local:
        return local
    # 触发 ModelScope / HF 镜像下载
    from download_model import ensure_bge_m3

    downloaded = ensure_bge_m3()
    local = _find_local_model()
    return local or downloaded or EMBEDDING_MODEL_HF


def _build_embedding_function() -> SentenceTransformerEmbeddingFunction:
    model_name = _resolve_model_name()
    print(f"[ChromaStore] 加载 BGE-M3 Embedding: {model_name}")
    return SentenceTransformerEmbeddingFunction(
        model_name=model_name,
        device="cpu",
        normalize_embeddings=True,
    )


def _distance_to_score(distance: float) -> float:
    """余弦距离转相似度（0~1，越大越相似）"""
    return max(0.0, min(1.0, 1.0 - float(distance)))


def _is_active(meta: dict | None) -> bool:
    """未标记 active 的历史记录视为有效"""
    if not meta:
        return True
    active = meta.get("active")
    if active is None:
        return True
    if isinstance(active, bool):
        return active
    if isinstance(active, str):
        return active.lower() not in ("false", "0", "no")
    return bool(active)


def _ticket_doc_id(ticket_id: str | int) -> str:
    return f"kb_ticket_{ticket_id}"


class ChromaStore:
    """ChromaDB 向量存储管理（接口与 FaissStore 兼容）"""

    def __init__(self):
        os.makedirs(CHROMA_PATH, exist_ok=True)
        self.embedding_fn = _build_embedding_function()
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self._init_collection()
        print(f"[ChromaStore] 集合 '{COLLECTION_NAME}' 当前 {self.count()} 条记录")

    def _init_collection(self):
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embedding_fn,
        )

    def _get_metadata_by_id(self, doc_id: str) -> dict:
        existing = self.collection.get(ids=[doc_id], include=["metadatas"])
        if not existing.get("ids"):
            return {}
        return dict(existing["metadatas"][0] or {})

    def _write_entry(
        self,
        doc_id: str,
        question: str,
        answer: str,
        metadata: dict,
    ) -> None:
        text = f"问题：{question}\n答案：{answer}"
        meta = dict(metadata)
        meta.update({"id": doc_id, "question": question, "answer": answer})
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[meta],
        )

    def _allocate_doc_id(self, metadata: dict) -> str:
        ticket_id = metadata.get("ticket_id")
        if ticket_id:
            return _ticket_doc_id(ticket_id)
        return f"kb_{self.count() + 1}"

    def _evaluate_similar_entries(
        self,
        question: str,
        answer: str,
        metadata: dict | None,
        dedup: bool,
        handle_conflicts: bool,
        dedup_threshold: float,
        conflict_threshold: float,
    ) -> dict | None:
        """检索相似条目并返回首个需要特殊处理的结果，无则返回 None（表示可直接新增）"""
        if self.count() == 0:
            return None
        if not dedup and not handle_conflicts:
            return None

        meta_ref = metadata if metadata is not None else {}

        existing_results = self.search(
            question, top_k=5, sort_by_priority=False
        )
        for r in existing_results:
            existing_id = r.get("id", "unknown")
            existing_meta = self._get_metadata_by_id(existing_id)
            similarity = effective_similarity_score(
                question,
                r.get("question", ""),
                r["score"],
                conflict_threshold,
            )
            plan = plan_import_action(
                new_answer=answer,
                new_metadata=meta_ref,
                existing_id=existing_id,
                existing_answer=r.get("answer", ""),
                existing_metadata=existing_meta,
                similarity_score=similarity,
                handle_conflicts=handle_conflicts,
                dedup_only=dedup and not handle_conflicts,
                conflict_threshold=conflict_threshold,
                dedup_threshold=dedup_threshold,
            )
            action = plan["action"]
            if action == "add":
                continue

            if action == "duplicate":
                print(
                    f"[ChromaStore] ⚠️ 去重跳过: 相似度={r['score']}, 已有ID={existing_id}"
                )
                return {
                    "id": existing_id,
                    "duplicate": True,
                    "conflict": False,
                    "action": "duplicate",
                    "message": plan["message"],
                    "existing_question": r.get("question"),
                    "score": r["score"],
                }

            if action == "coexist":
                boosted = plan.get("boosted_priority", get_priority(meta_ref) + 1)
                meta_ref["priority"] = boosted
                meta_ref["conflict_coexist"] = True
                print(
                    f"[ChromaStore] 📎 矛盾并存: 保留 ID={existing_id}, "
                    f"新条 priority={boosted}, 相似度={similarity:.2%}"
                )
                log_import_conflict(
                    question=question,
                    new_answer=answer,
                    new_metadata=meta_ref,
                    existing_id=existing_id,
                    existing_answer=r.get("answer", ""),
                    existing_metadata=existing_meta,
                    similarity_score=similarity,
                    action="coexist",
                )
                return None

            if action == "rejected":
                print(
                    f"[ChromaStore] ⚠️ 矛盾保留旧条: ID={existing_id}, 相似度={r['score']}"
                )
                log_import_conflict(
                    question=question,
                    new_answer=answer,
                    new_metadata=metadata,
                    existing_id=existing_id,
                    existing_answer=r.get("answer", ""),
                    existing_metadata=existing_meta,
                    similarity_score=r["score"],
                    action="rejected",
                )
                return {
                    "id": existing_id,
                    "duplicate": True,
                    "conflict": True,
                    "action": "rejected",
                    "message": plan["message"],
                    "existing_question": r.get("question"),
                    "score": r["score"],
                    "superseded_ids": [],
                }

            if action == "supersede":
                return self._supersede_entry(
                    old_id=existing_id,
                    old_meta=existing_meta,
                    question=question,
                    answer=answer,
                    metadata=metadata,
                    similarity_score=similarity,
                )
        return None

    def _supersede_entry(
        self,
        old_id: str,
        old_meta: dict,
        question: str,
        answer: str,
        metadata: dict | None,
        similarity_score: float,
    ) -> dict:
        """停用旧条目并写入更高优先级的新条目"""
        self.soft_delete(doc_id=old_id)

        meta = dict(metadata or {})
        meta.setdefault("active", True)
        canonical_id = old_meta.get("canonical_id") or old_id
        version = int(old_meta.get("version", 1) or 1) + 1
        meta["canonical_id"] = canonical_id
        meta["version"] = version
        meta["superseded_from"] = old_id
        meta["priority"] = max(get_priority(meta), get_priority(old_meta))

        doc_id = self._allocate_doc_id(meta)
        self._write_entry(doc_id, question, answer, meta)

        print(
            f"[ChromaStore] 🔄 矛盾覆盖: {old_id} → {doc_id} "
            f"(相似度={similarity_score:.2%}, priority={meta['priority']})"
        )
        log_import_conflict(
            question=question,
            new_answer=answer,
            new_metadata=meta,
            existing_id=old_id,
            existing_answer=old_meta.get("answer", ""),
            existing_metadata=old_meta,
            similarity_score=similarity_score,
            action="superseded",
        )
        return {
            "id": doc_id,
            "duplicate": False,
            "conflict": True,
            "action": "superseded",
            "message": f"矛盾知识已覆盖旧条 (旧={old_id}, 新={doc_id})",
            "score": similarity_score,
            "superseded_ids": [old_id],
            "canonical_id": canonical_id,
            "version": version,
        }

    def add(
        self,
        question: str,
        answer: str,
        metadata: dict = None,
        dedup: bool = True,
        dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
        handle_conflicts: bool = False,
        conflict_threshold: float = CONFLICT_SIMILARITY_THRESHOLD,
    ) -> dict:
        meta = dict(metadata or {})

        handled = self._evaluate_similar_entries(
            question=question,
            answer=answer,
            metadata=meta,
            dedup=dedup,
            handle_conflicts=handle_conflicts,
            dedup_threshold=dedup_threshold,
            conflict_threshold=conflict_threshold,
        )
        if handled is not None:
            return handled

        meta.setdefault("active", True)
        if "priority" not in meta:
            meta["priority"] = get_priority(meta)
        if "version" not in meta:
            meta["version"] = 1
        doc_id = self._allocate_doc_id(meta)
        self._write_entry(doc_id, question, answer, meta)
        print(f"[ChromaStore] ✅ 已添加: {doc_id} -> {question[:40]}...")
        return {
            "id": doc_id,
            "duplicate": False,
            "conflict": bool(meta.get("conflict_coexist")),
            "action": "added_coexist" if meta.get("conflict_coexist") else "added",
            "message": f"知识条目已入库 (ID: {doc_id})",
            "score": 1.0,
            "superseded_ids": [],
        }

    def batch_add(
        self,
        qa_pairs: list,
        dedup: bool = False,
        handle_conflicts: bool = True,
        conflict_threshold: float = CONFLICT_SIMILARITY_THRESHOLD,
    ) -> dict:
        added = 0
        skipped = 0
        superseded = 0
        rejected_conflicts = 0
        details = []

        for pair in qa_pairs:
            result = self.add(
                question=pair["question"],
                answer=pair["answer"],
                metadata=pair.get("metadata"),
                dedup=dedup,
                handle_conflicts=handle_conflicts,
                conflict_threshold=conflict_threshold,
            )
            details.append(result)
            action = result.get("action", "added")
            if action in ("duplicate", "rejected"):
                skipped += 1
                if result.get("conflict"):
                    rejected_conflicts += 1
            elif action == "superseded":
                added += 1
                superseded += 1
            else:
                added += 1

        print(
            f"[ChromaStore] 批量添加: 新增 {added} 条"
            f"(覆盖 {superseded}), 跳过 {skipped} 条"
            f"(矛盾保留 {rejected_conflicts}), 总计 {self.count()} 条"
        )
        return {
            "added": added,
            "skipped": skipped,
            "superseded": superseded,
            "rejected_conflicts": rejected_conflicts,
            "details": details,
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        active_only: bool = True,
        sort_by_priority: bool = True,
        max_answers: int | None = None,
    ) -> list:
        total = self.count()
        if total == 0:
            return []

        limit = max_answers or top_k
        fetch_k = min(max(limit * 8, top_k * 5, limit), total)
        results = self.collection.query(
            query_texts=[query],
            n_results=fetch_k,
            include=["metadatas", "documents", "distances"],
        )

        output = []
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            meta = metadatas[i] or {}
            if active_only and not _is_active(meta):
                continue
            score = round(_distance_to_score(distances[i]), 4)
            question = meta.get("question", "")
            answer = meta.get("answer", "")
            priority = int(meta.get("priority", get_priority(meta)))
            version = meta.get("version")
            date_val = meta.get("date") or meta.get("revision_date") or ""
            output.append(
                {
                    "id": meta.get("id", doc_id),
                    "question": question,
                    "answer": answer,
                    "score": score,
                    "priority": priority,
                    "version": int(version) if version is not None else None,
                    "date": str(date_val) if date_val else None,
                    "metadata": dict(meta),
                    "document": f"问题：{question}\n答案：{answer}",
                }
            )

        if sort_by_priority:
            output = sort_search_results(output)

        return output[:limit]

    def soft_delete(
        self,
        doc_id: str | None = None,
        ticket_id: str | int | None = None,
    ) -> dict:
        """软删除：标记 active=false，检索与去重时自动忽略"""
        target_id = doc_id
        if ticket_id is not None:
            target_id = _ticket_doc_id(ticket_id)
        if not target_id:
            return {"success": False, "message": "必须提供 id 或 ticket_id"}

        existing = self.collection.get(ids=[target_id], include=["metadatas"])
        if not existing.get("ids"):
            return {
                "success": False,
                "message": f"知识条目不存在: {target_id}",
                "id": target_id,
            }

        meta = dict(existing["metadatas"][0] or {})
        if not _is_active(meta):
            return {
                "success": True,
                "message": f"知识条目已是停用状态 (ID: {target_id})",
                "id": target_id,
                "already_inactive": True,
            }

        meta["active"] = False
        self.collection.update(ids=[target_id], metadatas=[meta])
        print(f"[ChromaStore] 🗑️ 已软删除: {target_id}")
        return {
            "success": True,
            "message": f"知识条目已停用 (ID: {target_id})",
            "id": target_id,
            "already_inactive": False,
        }

    def count(self) -> int:
        return self.collection.count()

    def count_active(self) -> int:
        total = self.count()
        if total == 0:
            return 0
        all_meta = self.collection.get(include=["metadatas"])["metadatas"]
        return sum(1 for m in all_meta if _is_active(m))

    def clear(self):
        import gc
        import time

        try:
            self.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        # 必须先释放 Chroma 客户端，否则 sqlite 文件仍被占用
        self.collection = None
        self.client = None
        gc.collect()
        time.sleep(0.3)

        if os.path.isdir(CHROMA_PATH):
            shutil.rmtree(CHROMA_PATH, ignore_errors=True)
        os.makedirs(CHROMA_PATH, exist_ok=True)

        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self._init_collection()
        print("[ChromaStore] 知识库已清空")


store = ChromaStore()
