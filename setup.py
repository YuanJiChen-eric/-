import os
from modelscope import snapshot_download

print("=== 开始一键高速补全所有离线模型（ModelScope 国内节点） ===")

# 1. 下载 BAAI/bge-small-zh 到根目录的 local_models
print("\n1/3 正在下载 RAG 嵌入模型 [bge-small-zh] ...")
snapshot_download("BAAI/bge-small-zh", cache_dir="./local_models")

# 2. 下载 BAAI/bge-reranker-base 到根目录的 model_cache
print("\n2/3 正在下载重排序模型 [bge-reranker-base] ...")
snapshot_download("BAAI/bge-reranker-base", cache_dir="./model_cache")

# 3. 下载 sentence-transformers/all-MiniLM-L6-v2 到 kb_service/local_models
print("\n3/3 正在下载 FAISS 向量模型 [all-MiniLM-L6-v2] ...")
snapshot_download("sentence-transformers/all-MiniLM-L6-v2", cache_dir="./kb_service/local_models")

print("\n[成功] 所有的模型均已高速补全！可以开始启动服务。")