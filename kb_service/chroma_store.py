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

    def add(
        self,
        question: str,
        answer: str,
        metadata: dict = None,
        dedup: bool = True,
        dedup_threshold: float = 0.90,
    ) -> dict:
        if dedup and self.count() > 0:
            existing_results = self.search(question, top_k=3)
            for r in existing_results:
                if r["score"] >= dedup_threshold:
                    dup_id = r.get("id", "unknown")
                    print(
                        f"[ChromaStore] ⚠️ 去重跳过: 相似度={r['score']}, 已有ID={dup_id}"
                    )
                    return {
                        "id": dup_id,
                        "duplicate": True,
                        "message": (
                            f"已存在相似记录 (相似度={r['score']:.2%}, ID={dup_id})，跳过新增"
                        ),
                        "existing_question": r["question"],
                        "score": r["score"],
                    }

        meta = dict(metadata or {})
        meta.setdefault("active", True)
        ticket_id = meta.get("ticket_id")
        if ticket_id:
            doc_id = _ticket_doc_id(ticket_id)
        else:
            doc_id = f"kb_{self.count() + 1}"
        text = f"问题：{question}\n答案：{answer}"
        meta.update({"id": doc_id, "question": question, "answer": answer})

        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[meta],
        )
        print(f"[ChromaStore] ✅ 已添加: {doc_id} -> {question[:40]}...")
        return {
            "id": doc_id,
            "duplicate": False,
            "message": f"知识条目已入库 (ID: {doc_id})",
            "score": 1.0,
        }

    def batch_add(self, qa_pairs: list, dedup: bool = False) -> dict:
        added = 0
        skipped = 0
        details = []

        for pair in qa_pairs:
            result = self.add(
                question=pair["question"],
                answer=pair["answer"],
                metadata=pair.get("metadata"),
                dedup=dedup,
            )
            details.append(result)
            if result.get("duplicate"):
                skipped += 1
            else:
                added += 1

        print(
            f"[ChromaStore] 批量添加: 新增 {added} 条, 跳过 {skipped} 条, 总计 {self.count()} 条"
        )
        return {"added": added, "skipped": skipped, "details": details}

    def search(self, query: str, top_k: int = 5, active_only: bool = True) -> list:
        total = self.count()
        if total == 0:
            return []

        fetch_k = min(max(top_k * 5, top_k), total)
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
            output.append(
                {
                    "id": meta.get("id", doc_id),
                    "question": question,
                    "answer": answer,
                    "score": score,
                    "document": f"问题：{question}\n答案：{answer}",
                }
            )
            if len(output) >= top_k:
                break
        return output

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
