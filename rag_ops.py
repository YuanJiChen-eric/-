import os
import re
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
    search_kwargs={"score_threshold": 0.60, "k": 5}
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


KB_MAX_ANSWERS = 3
KB_SEARCH_URL = "http://127.0.0.1:8000/api/kb/search"
MIN_KB_SCORE = 0.60  # 拒答阈值：与 kb_service 过滤逻辑对齐，低于 60% 视为未命中
REFUSE_ANSWER = "抱歉，我暂时无法处理该问题。请点击转人工，运维工程师将稍后联系您。"
GREETING_ANSWER = (
    "您好！我是运维智能助手，可协助处理账号、VPN、磁盘、服务器等运维问题。"
    "请直接描述您遇到的问题，例如「账号冻结怎么处理」。"
)
META_NO_HISTORY_ANSWER = (
    "我基于每次提问单独作答，不自动记忆更早的对话。"
    "请向上翻看本页聊天记录；如需继续处理，请直接说明您的运维问题。"
)
KB_ADMIN_ANSWER = (
    "聊天窗口不能直接修改知识库。知识库更新通常通过以下方式：\n\n"
    "1. **数据飞轮（推荐）**：运维在后台处理完工单后，系统会自动将「用户问题 + 标准答案」写入向量库；\n"
    "2. **批量导入**：将 ops_docs 运维文档放入目录后，在 kb_service 侧执行 ingest 脚本切片入库；\n"
    "3. **人工维护**：大批量变更或特殊条目，请联系知识库管理员，或点击转人工说明需求。"
)

_META_QUESTION_PATTERNS = [
    re.compile(p)
    for p in [
        r"(刚才|刚刚|之前|上文|上一轮).*(说|聊|问|提到)",
        r"(我们|咱).*(说了|聊了|谈到|提到).*(什么|啥)",
        r"聊了(什么|啥)",
        r"你还记得",
        r"总结.*(聊|对话|会话)",
        r"(刚|刚才)问",
        r"说到哪了",
        r"聊到哪",
    ]
]

_SMALL_TALK_EXACT = {
    "你好", "您好", "hi", "hello", "在吗", "你是谁", "你是什么", "介绍一下自己",
}

_KB_ADMIN_PATTERNS = [
    re.compile(p)
    for p in [
        r"更新.*知识库",
        r"知识库.*(更新|入库|添加|录入|维护|修改|删除|扩充)",
        r"(添加|录入|入库|更新|修改).*(知识|问答|FAQ|词条)",
        r"怎么.*(维护|管理).*知识库",
        r"如何.*(维护|管理|更新).*知识库",
    ]
]


def is_meta_conversation_question(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return any(p.search(t) for p in _META_QUESTION_PATTERNS)


def is_small_talk(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return t.lower() in _SMALL_TALK_EXACT or t in _SMALL_TALK_EXACT


def is_kb_admin_intent(text: str) -> bool:
    """用户想维护/更新知识库本身，不应走故障知识检索"""
    t = (text or "").strip()
    if not t:
        return False
    return any(p.search(t) for p in _KB_ADMIN_PATTERNS)


def answer_meta_from_history(question: str, history: list | None) -> str:
    """会话回顾类问题：用前端传来的历史回答，不走知识库检索"""
    if not history:
        return META_NO_HISTORY_ANSWER

    lines: list[str] = []
    for msg in history[-12:]:
        role = (msg.get("role") or "").lower()
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        speaker = "您" if role == "user" else "助手"
        if len(content) > 300:
            content = content[:300] + "…"
        lines.append(f"- {speaker}：{content}")

    if not lines:
        return META_NO_HISTORY_ANSWER

    return (
        "根据当前会话记录，我们最近的交流如下：\n\n"
        + "\n".join(lines)
        + "\n\n如需继续处理运维问题，请直接提问。"
    )


def get_kb_documents(query: str, max_answers: int = KB_MAX_ANSWERS) -> list:
    """从 8000 知识库拉取最多 max_answers 条，保持服务端 priority 排序"""
    try:
        payload = {
            "query": query,
            "top_k": max(max_answers, 5),
            "max_answers": max_answers,
            "sort_by_priority": True,
        }
        response = requests.post(KB_SEARCH_URL, json=payload, timeout=5)
        if response.status_code == 200:
            response.encoding = "utf-8"
            res_json = response.json()

            results = []
            if isinstance(res_json, dict):
                results = res_json.get("results", [])
            elif isinstance(res_json, list):
                results = res_json

            docs = []
            seen_answers: set[str] = set()
            for r in results:
                q = r.get("question", "")
                a = r.get("answer", "")
                if not (q and a):
                    continue
                ans_key = a.strip().lower()
                if ans_key in seen_answers:
                    continue
                seen_answers.add(ans_key)

                priority = r.get("priority")
                kb_id = r.get("id", "")
                version = r.get("version")
                date = r.get("date")
                score = r.get("score")
                if score is not None and score < MIN_KB_SCORE:
                    continue

                prio_label = priority if priority is not None else "—"
                header = f"参考（priority={prio_label}, id={kb_id}"
                if version is not None:
                    header += f", v={version}"
                if date:
                    header += f", date={date}"
                header += f", 相似度={score:.0%}" if score else ""
                header += "）"
                content = f"{header}\n问题：{q}\n方案：{a}"
                docs.append(
                    Document(
                        page_content=content,
                        metadata={
                            "source": "kb_service_dynamic",
                            "kb_id": kb_id,
                            "priority": priority,
                            "version": version,
                            "date": date,
                            "score": score,
                            "question": q,
                            "answer": a,
                        },
                    )
                )
                if len(docs) >= max_answers:
                    break
            return docs
    except Exception as e:
        print(f"[RAG] ⚠️ 请求 8000 端口同步知识库失败 (可能服务未启动): {e}")
    return []


def _dedupe_kb_documents(kb_docs: list) -> list:
    """相同答案只占一条，留出空位给 knowledge.txt 等本地参考"""
    seen: set[str] = set()
    out = []
    for doc in kb_docs:
        answer = (doc.metadata.get("answer") or "").strip().lower()
        if answer and answer in seen:
            continue
        if answer:
            seen.add(answer)
        out.append(doc)
    return out


def build_context_documents(query: str, raw_docs: list, kb_docs: list) -> list:
    """
    组装送入模型的上下文：
    - 8000 知识库条目已按 priority 排序，去重后取前 N 条
    - 不足时用 knowledge.txt 本地检索补足（避免重复种子 FAQ 占满 3 条）
    """
    context_docs: list = []

    if kb_docs:
        deduped = _dedupe_kb_documents(kb_docs)
        context_docs.extend(deduped[:KB_MAX_ANSWERS])

    remaining = KB_MAX_ANSWERS - len(context_docs)
    if remaining > 0 and raw_docs:
        local_docs = rerank_documents(query, raw_docs, top_k=remaining)
        context_docs.extend(local_docs)

    if not context_docs and raw_docs:
        context_docs = rerank_documents(query, raw_docs, top_k=KB_MAX_ANSWERS)

    return context_docs


def _extract_sources(context_docs: list) -> list:
    sources = []
    for doc in context_docs:
        meta = doc.metadata or {}
        if meta.get("source") != "kb_service_dynamic":
            continue
        sources.append(
            {
                "id": meta.get("kb_id", ""),
                "question": meta.get("question", ""),
                "answer": meta.get("answer", ""),
                "priority": meta.get("priority"),
                "version": meta.get("version"),
                "date": meta.get("date"),
                "score": meta.get("score"),
            }
        )
    return sources


def _answers_are_distinct(sources: list) -> bool:
    texts = {(s.get("answer") or "").strip().lower() for s in sources}
    texts.discard("")
    return len(texts) >= 2


def _kb_top_score(sources: list) -> float:
    if not sources:
        return 0.0
    return max((s.get("score") or 0.0) for s in sources)


def format_multi_kb_answer(sources: list, question: str) -> str | None:
    """多条知识库参考且答案不同、且相似度达标时，直接拼出多答案（不依赖小模型）"""
    if len(sources) < 2 or not _answers_are_distinct(sources):
        return None
    if _kb_top_score(sources) < MIN_KB_SCORE:
        return None

    lines = [
        f"关于「{question}」，知识库中有 {min(len(sources), KB_MAX_ANSWERS)} 条相关参考（按 priority 从高到低）：",
        "",
    ]
    for i, s in enumerate(sources[:KB_MAX_ANSWERS], 1):
        label = "推荐" if i == 1 else f"备选{i - 1}"
        prio = s.get("priority", "—")
        score = s.get("score")
        score_txt = f"，相似度 {score:.0%}" if isinstance(score, (int, float)) else ""
        lines.append(f"【参考{i}·{label}】priority={prio}{score_txt}")
        if s.get("question"):
            lines.append(f"问题：{s['question']}")
        lines.append(f"方案：{s.get('answer', '')}")
        lines.append("")

    lines.append("——")
    lines.append("多条参考并存时，默认优先采纳 priority 较高的方案；仍有疑问请转人工确认。")
    return "\n".join(lines)


def _parse_doc_qa(doc: Document) -> tuple[str, str]:
    """从 Document 中解析问题与方案"""
    meta = doc.metadata or {}
    question = meta.get("question") or ""
    answer = meta.get("answer") or ""
    text = doc.page_content or ""

    if not question and "问题：" in text:
        question = text.split("问题：", 1)[1].split("\n", 1)[0].strip()
    if not question and text.lstrip().startswith("## "):
        question = text.lstrip().split("\n", 1)[0].replace("## ", "").strip()

    if not answer and "方案：" in text:
        after = text.split("方案：", 1)[1]
        answer_lines: list[str] = []
        for line in after.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## "):
                break
            if stripped:
                answer_lines.append(stripped)
        answer = answer_lines[0] if answer_lines else after.strip().split("\n", 1)[0].strip()

    return question, answer


def _has_local_reference(context_docs: list) -> bool:
    return any(
        (doc.metadata or {}).get("source") != "kb_service_dynamic"
        for doc in context_docs
    )


def format_direct_answer(context_docs: list, question: str) -> str | None:
    """
    知识库命中或本地 knowledge.txt 有方案时，直接输出方案（避免小模型复读问句）。
    """
    if not context_docs:
        return None

    sources = _extract_sources(context_docs)
    top_score = (sources[0].get("score") if sources else None) or 0.0
    has_local = _has_local_reference(context_docs)

    if sources and top_score < MIN_KB_SCORE:
        return None
    if not sources and has_local:
        # 仅有本地手册命中、知识库无可靠结果时不直出，避免弱匹配凑答案
        return None

    lines = ["根据知识库与运维手册，为您找到以下方案：", ""]
    seen_answers: set[str] = set()
    ref_idx = 0

    for doc in context_docs:
        q, a = _parse_doc_qa(doc)
        if not a:
            continue
        ans_key = a.strip().lower()
        if ans_key in seen_answers:
            continue
        seen_answers.add(ans_key)
        ref_idx += 1

        meta = doc.metadata or {}
        score = meta.get("score")
        label = f"参考{ref_idx}"
        if score is not None:
            label += f"（相似度 {score:.0%}）"
        elif meta.get("source") != "kb_service_dynamic":
            label += "（运维手册）"

        lines.append(f"【{label}】")
        lines.append(f"问题：{q or question}")
        lines.append(f"方案：{a}")
        lines.append("")

        if ref_idx >= KB_MAX_ANSWERS:
            break

    if ref_idx == 0:
        return None

    return "\n".join(lines).strip()


def _generate_answer(question: str, context_docs: list) -> tuple[str, list]:
    sources = _extract_sources(context_docs)
    multi = format_multi_kb_answer(sources, question)
    if multi:
        return multi, sources

    direct = format_direct_answer(context_docs, question)
    if direct:
        return direct, sources

    context = "\n\n---\n\n".join([doc.page_content for doc in context_docs])
    formatted_prompt = PROMPT.format(context=context, question=question)
    answer = llm.invoke(formatted_prompt)
    answer = answer.replace("tickets.com", "ticket.company.com")
    answer = answer.replace("your-computer.company.com", "")
    if answer.startswith("回答："):
        answer = answer[3:].strip()
    return answer, sources

# -------------------- 5. Prompt（支持多条参考、语义匹配） --------------------
prompt_template = """你是运维数字员工，依据【已知信息】回答用户运维问题。

规则：
1. 用户问题与已知信息语义相关即可，不要求与「问题：」一行文字完全一致。
2. 已知信息可能包含 1～3 条参考，已按 priority 从高到低排列（priority 越大越权威）。
3. 回答方式：
   - 仅 1 条：概括该条「方案：」中的要点，保留命令、URL、电话等原文。
   - 2～3 条且内容一致：合并为一条清晰回答。
   - 2～3 条且内容矛盾：按 priority 从高到低分别列出，例如「参考1（推荐）」「参考2（备选）」，不要只写其中一条。
4. 不要编造已知信息中没有的内容。
5. 若已知信息不足以回答，回复：“抱歉，我暂时无法处理该问题。请点击转人工，运维工程师将稍后联系您。”

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
        answer = REFUSE_ANSWER
        print(f"问：{query}\n答：{answer}\n（非运维话题）")
        return answer, []

    try:
        raw_docs = retriever.invoke(query)
    except:
        raw_docs = []

    kb_docs = get_kb_documents(query)
    context_docs = build_context_documents(query, raw_docs, kb_docs)

    if not context_docs:
        answer = REFUSE_ANSWER
        print(f"问：{query}\n答：{answer}\n（无相关文档）")
        return answer, []

    sources = _extract_sources(context_docs)
    if sources and _kb_top_score(sources) < MIN_KB_SCORE:
        answer = REFUSE_ANSWER
        print(f"问：{query}\n答：{answer}\n（知识库匹配度不足）")
        return answer, []

    answer, _ = _generate_answer(query, context_docs)
    answer = answer.replace(
        "https://your-computer.company.com/", "http://selfservice.company.com/unfreeze"
    )
    answer = answer.replace("## 答案：", "").strip()

    print(f"问：{query}")
    print(f"答：{answer}")
    return answer, context_docs

# -------------------- 8. API --------------------
def get_answer(question: str, history: list | None = None) -> dict:
    if is_meta_conversation_question(question):
        return {
            "success": True,
            "answer": answer_meta_from_history(question, history),
            "need_human": False,
            "sources": [],
        }

    if is_small_talk(question):
        return {
            "success": True,
            "answer": GREETING_ANSWER,
            "need_human": False,
            "sources": [],
        }

    if is_kb_admin_intent(question):
        return {
            "success": True,
            "answer": KB_ADMIN_ANSWER,
            "need_human": False,
            "sources": [],
        }

    forbid_keywords = ["天气", "下雨", "下雪", "电影", "音乐", "游戏", "笑话", "故事"]
    if any(kw in question for kw in forbid_keywords):
        return {
            "success": True,
            "answer": REFUSE_ANSWER,
            "need_human": True,
            "sources": [],
        }

    try:
        raw_docs = retriever.invoke(question)
    except:
        raw_docs = []
        
    kb_docs = get_kb_documents(question)
    context_docs = build_context_documents(question, raw_docs, kb_docs)

    if not context_docs:
        return {
            "success": True,
            "answer": REFUSE_ANSWER,
            "need_human": True,
            "sources": [],
        }

    sources = _extract_sources(context_docs)
    if sources and _kb_top_score(sources) < MIN_KB_SCORE:
        return {
            "success": True,
            "answer": REFUSE_ANSWER,
            "need_human": True,
            "sources": [],
        }

    answer, sources = _generate_answer(question, context_docs)
    need_human = answer == REFUSE_ANSWER or (
        answer.startswith("抱歉") and "无法处理" in answer
    )
    return {
        "success": True,
        "answer": answer,
        "need_human": need_human,
        "sources": sources,
    }