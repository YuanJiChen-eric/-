"""
FAISS 向量知识库封装（已弃用）

请使用 chroma_store.py（ChromaDB + BGE-M3）。
本文件保留仅供回滚参考，不再被 main.py / rebuild_kb.py 引用。
"""
import os
# 设置 HuggingFace 国内镜像，解决国内网络无法访问 huggingface.co 的问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import numpy as np
import json
from sentence_transformers import SentenceTransformer

# 持久化路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAISS_PATH = os.path.join(BASE_DIR, "faiss_store")
INDEX_FILE = os.path.join(FAISS_PATH, "index.faiss")
META_FILE = os.path.join(FAISS_PATH, "metadata.json")

# Embedding 模型（轻量快速，适合 Mac 8GB 内存）
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class FaissStore:
    """FAISS 向量存储管理"""

    def __init__(self):
        os.makedirs(FAISS_PATH, exist_ok=True)
        print(f"[FAISSStore] 加载 Embedding 模型: {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        # 兼容新旧版本的维度获取方法
        if hasattr(self.model, "get_sentence_embedding_dimension"):
            self.dimension = self.model.get_sentence_embedding_dimension()
        else:
            self.dimension = self.model.get_embedding_dimension()
        print(f"[FAISSStore] 向量维度: {self.dimension}")

        self.index = None
        self.metadata = []  # 每条记录的元数据（question, answer, ...）
        self._load_or_create()

    def _load_or_create(self):
        """加载已有索引，或创建新索引"""
        try:
            import faiss
            if os.path.exists(INDEX_FILE) and os.path.exists(META_FILE):
                self.index = faiss.read_index(INDEX_FILE)
                with open(META_FILE, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                print(f"[FAISSStore] 已加载索引，当前 {len(self.metadata)} 条记录")
            else:
                self.index = faiss.IndexFlatL2(self.dimension)
                self.metadata = []
                print(f"[FAISSStore] 新建空索引")
        except Exception as e:
            import faiss
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
            print(f"[FAISSStore] 索引初始化: {e}")

    def _save(self):
        """持久化索引和元数据"""
        import faiss, json
        os.makedirs(FAISS_PATH, exist_ok=True)
        faiss.write_index(self.index, INDEX_FILE)
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        print(f"[FAISSStore] 已保存到 {FAISS_PATH}")

    def add(self, question: str, answer: str, metadata: dict = None,
            dedup: bool = True, dedup_threshold: float = 0.90) -> dict:
        """
        添加一条 Q&A 到知识库，返回 {"id": str, "duplicate": bool, "message": str}

        参数:
            question: 问题文本
            answer: 答案文本
            metadata: 额外元数据
            dedup: 是否启用语义去重（默认 True）
            dedup_threshold: 语义相似度阈值（0~1，默认 0.90，超过即视为重复）
        """
        import json

        # ── 语义去重：搜索已有记录，检查是否存在相似问题 ──
        if dedup and len(self.metadata) > 0:
            existing_results = self.search(question, top_k=3)
            for r in existing_results:
                if r["score"] >= dedup_threshold:
                    # 找到重复记录，跳过新增
                    dup_id = r.get("id", "unknown")
                    print(f"[FAISSStore] ⚠️ 去重跳过: 与已有记录高度相似 (相似度={r['score']}, 已有ID={dup_id})")
                    print(f"           新问题: {question[:50]}...")
                    print(f"           已有问题: {r['question'][:50]}...")
                    return {
                        "id": dup_id,
                        "duplicate": True,
                        "message": f"已存在相似记录 (相似度={r['score']:.2%}, ID={dup_id})，跳过新增",
                        "existing_question": r["question"],
                        "score": r["score"]
                    }

        doc_id = f"kb_{len(self.metadata) + 1}"
        # 嵌入向量（用 question + answer 拼接）
        text = f"问题：{question}\n答案：{answer}"
        embedding = self.model.encode([text])[0].astype(np.float32)
        embedding = embedding.reshape(1, -1)

        self.index.add(embedding)
        meta = metadata or {}
        meta["id"] = doc_id
        meta["question"] = question
        meta["answer"] = answer
        self.metadata.append(meta)
        self._save()
        print(f"[FAISSStore] ✅ 已添加: {doc_id} -> {question[:40]}...")
        return {
            "id": doc_id,
            "duplicate": False,
            "message": f"知识条目已入库 (ID: {doc_id})",
            "score": 1.0
        }

    def batch_add(self, qa_pairs: list, dedup: bool = False) -> dict:
        """
        批量添加 Q&A 对

        qa_pairs: [{"question": "...", "answer": "...", "metadata": {...}}, ...]
        dedup: 是否启用去重（批量默认关闭，因为 seed_data 不需要）
        返回: {"added": int, "skipped": int, "details": [...]}
        """
        import json
        added = 0
        skipped = 0
        details = []

        for pair in qa_pairs:
            result = self.add(
                question=pair["question"],
                answer=pair["answer"],
                metadata=pair.get("metadata"),
                dedup=dedup
            )
            details.append(result)
            if result.get("duplicate"):
                skipped += 1
            else:
                added += 1

        print(f"[FAISSStore] 批量添加: 新增 {added} 条, 跳过 {skipped} 条, 总计 {len(self.metadata)} 条")
        return {"added": added, "skipped": skipped, "details": details}

    def search(self, query: str, top_k: int = 5) -> list:
        """
        检索最相关的 top_k 条记录
        返回: [{"question": "...", "answer": "...", "score": 0.95}, ...]
        """
        if len(self.metadata) == 0:
            return []

        query_embedding = self.model.encode([query])[0].astype(np.float32).reshape(1, -1)
        actual_k = min(top_k, len(self.metadata))
        distances, indices = self.index.search(query_embedding, actual_k)

        output = []
        for i in range(actual_k):
            idx = int(indices[0][i])
            if idx < len(self.metadata):
                meta = self.metadata[idx]
                distance = float(distances[0][i])
                # L2 距离转相似度（约 0~1，越小越相似）
                score = max(0, 1 - distance / 10)
                output.append({
                    "id": meta.get("id", ""),
                    "question": meta.get("question", ""),
                    "answer": meta.get("answer", ""),
                    "score": round(score, 4),
                    "document": f"问题：{meta.get('question', '')}\n答案：{meta.get('answer', '')}"
                })
        return output

    def count(self) -> int:
        """返回知识库总条数"""
        return len(self.metadata)

    def clear(self):
        """清空知识库"""
        import faiss
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        self._save()
        print("[FAISSStore] 知识库已清空")


# 全局单例
store = FaissStore()
