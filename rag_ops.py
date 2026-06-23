import os
import requests
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document  # 导入文档类
from sentence_transformers import CrossEncoder
from modelscope import snapshot_download

# -------------------- 1. 加载与切分 --------------------
loader = TextLoader("knowledge.txt", encoding="utf-8")
documents = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=80,
    separators=["\n\n", "\n", "。", "？", "；", "，", " ", ""]
)
docs = text_splitter.split_documents(documents)

# -------------------- 2. 嵌入模型与向量数据库 --------------------
embedding_model = HuggingFaceEmbeddings(
    model_name="./local_models/BAAI/bge-small-zh",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

persist_directory = "chroma_db"
# 💡 优化点 1：移除 shutil.rmtree，防止每次启动服务都被格式化清空本地数据
# if os.path.exists(persist_directory):
#     import shutil
#     shutil.rmtree(persist_directory)

vectordb = Chroma.from_documents(
    documents=docs,
    embedding=embedding_model,
    persist_directory=persist_directory
)

# -------------------- 3. 检索器 --------------------
retriever = vectordb.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.35, "k": 5}
)

# -------------------- 4. 重排序模型 --------------------
reranker = None
print("正在通过 ModelScope 加载重排序模型 BAAI/bge-reranker-base ...")
try:
    model_dir = snapshot_download("BAAI/bge-reranker-base", cache_dir="./model_cache")
    reranker = CrossEncoder(model_dir, max_length=512)
    print(f"重排序模型加载成功！模型缓存路径：{model_dir}")
except Exception as e:
    print(f"重排序模型加载失败，将使用基础检索结果。错误信息：{e}")

def rerank_documents(query, docs, top_k=2):
    if not docs:
        return []
    if reranker is None:
        return docs[:top_k]
    pairs = [[query, doc.page_content] for doc in docs]
    scores = reranker.predict(pairs)
    scored_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, score in scored_docs[:top_k]]

# 💡 终极修复：安全提取结果并强制 UTF-8 编码
def get_kb_documents(query: str) -> list:
    try:
        url = "http://127.0.0.1:8000/api/kb/search"
        payload = {"query": query, "question": query}
        response = requests.post(url, json=payload, timeout=3)
        if response.status_code == 200:
            # 1. 强行指定 UTF-8 解码，彻底解决 ä¸åå»... 这种中文乱码隐患
            response.encoding = 'utf-8'
            res_json = response.json()
            
            # 2. 核心修复：从字典中取出真正的 "results" 列表，避免 string indices 报错
            results = []
            if isinstance(res_json, dict):
                results = res_json.get("results", [])
            elif isinstance(res_json, list):
                results = res_json

            docs = []
            for r in results:
                # 3. 安全读取，并对齐大模型严格要求的 ## 和 方案：格式
                q = r.get("question", "")
                a = r.get("answer", "")
                if q and a:
                    content = f"## {q}\n方案：{a}"
                    docs.append(Document(page_content=content, metadata={"source": "kb_service_dynamic"}))
            return docs
    except Exception as e:
        print(f"[RAG] ⚠️ 请求 8000 端口同步知识库失败 (可能服务未启动): {e}")
    return []

# -------------------- 5. Prompt（强化复刻） --------------------
prompt_template = """你是运维数字员工，只能依据【已知信息】回答，且必须完全复制已知信息中的步骤、网址和电话号码，不得做任何修改。

规则：
1. 检查用户问题与已知信息中的标签（## 开头）是否完全匹配。若不匹配，必须拒答。
2. 回答时，将匹配条目的“方案：”后面的内容一字不差地输出，不添加任何解释。
3. 如果已知信息不含解决方案，回复：“抱歉，我暂时无法处理该问题。请点击转人工，运维工程师将稍后联系您。”

已知信息：
{context}

用户问题：{question}
回答："""

PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

# -------------------- 6. LLM --------------------
llm = OllamaLLM(model="deepseek-r1:1.5b", temperature=0)

# -------------------- 7. 问答函数 --------------------
def ask(query):
    forbid_keywords = ["天气", "下雨", "下雪", "电影", "音乐", "游戏", "笑话", "故事"]
    if any(kw in query for kw in forbid_keywords):
        answer = "抱歉，我暂时无法处理该问题。请点击转人工，运维工程师将稍后联系您。"
        print(f"问：{query}\n答：{answer}\n（非运维话题）")
        return answer, []

    try:
        raw_docs = retriever.invoke(query)
    except:
        raw_docs = []

    # 合并来自 8000 端口同步写入的动态数据
    kb_docs = get_kb_documents(query)
    all_docs = raw_docs + kb_docs

    if not all_docs:
        answer = "抱歉，我暂时无法处理该问题。请点击转人工，运维工程师将稍后联系您。"
        print(f"问：{query}\n答：{answer}\n（无相关文档）")
        return answer, []

    top_docs = rerank_documents(query, all_docs, top_k=2)
    context = "\n\n".join([doc.page_content for doc in top_docs])

    formatted_prompt = PROMPT.format(context=context, question=query)
    answer = llm.invoke(formatted_prompt)

    # 后处理
    answer = answer.replace("tickets.com", "ticket.company.com")
    answer = answer.replace("your-computer.company.com", "http://selfservice.company.com/unfreeze")
    answer = answer.replace("https://your-computer.company.com/", "http://selfservice.company.com/unfreeze")
    answer = answer.replace("## 答案：", "").replace("回答：", "").strip()

    print(f"问：{query}")
    print(f"答：{answer}")
    return answer, top_docs

# -------------------- 8. API --------------------
def get_answer(question: str) -> dict:
    try:
        raw_docs = retriever.invoke(question)
    except:
        raw_docs = []
        
    # 同步拉取来自 8000 端口的数据
    kb_docs = get_kb_documents(question)
    all_docs = raw_docs + kb_docs

    if not all_docs:
        return {"success": True, "answer": "抱歉，我暂时无法处理该问题。请点击转人工，运维工程师将稍后联系您。", "need_human": True}
        
    top_docs = rerank_documents(question, all_docs, top_k=2)
    context = "\n\n".join([doc.page_content for doc in top_docs])
    formatted_prompt = PROMPT.format(context=context, question=question)
    answer = llm.invoke(formatted_prompt)
    answer = answer.replace("tickets.com", "ticket.company.com")
    answer = answer.replace("your-computer.company.com", "")
    need_human = "无法处理" in answer or "转人工" in answer
    return {"success": True, "answer": answer, "need_human": need_human}