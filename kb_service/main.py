"""
运维知识库服务 - FastAPI
暴露接口：
  POST /api/kb/add    - 添加 Q&A 对到知识库（Java 后端调用）
  GET  /api/kb/search - 检索知识库（调试用）
  GET  /api/kb/count  - 查看知识库条数
  GET  /api/kb/health - 健康检查
  POST /api/rag       - RAG智能问答（核心功能）
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from chroma_store import store
from kb_conflict import MAX_ANSWERS_PER_QUERY
import uvicorn
import json
import time

# ─────────────── 数据模型 ───────────────

class AddKnowledgeRequest(BaseModel):
    """Java 后端调用 /api/kb/add 时的请求体"""
    question: str = Field(..., description="用户原始问题", min_length=1)
    answer: str = Field(..., description="人工修正后的正确答案", min_length=1)
    skip_if_duplicate: bool = Field(default=True, description="是否开启语义去重（默认开启）")
    dedup_threshold: float = Field(default=0.90, ge=0.5, le=1.0, description="去重相似度阈值")
    handle_conflicts: bool = Field(default=True, description="导入矛盾检测与优先级仲裁")
    conflict_threshold: float = Field(
        default=0.80, ge=0.5, le=1.0, description="矛盾检测相似度阈值"
    )
    metadata: dict | None = Field(default=None, description="附加元数据，如 ticket_id、source")

class AddKnowledgeResponse(BaseModel):
    success: bool
    id: str
    message: str
    duplicate: bool = False
    conflict: bool = False
    action: str = "added"
    score: float | None = None
    existing_question: str | None = None
    superseded_ids: list[str] = Field(default_factory=list)

class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询", min_length=1)
    top_k: int = Field(5, ge=1, le=20, description="返回条数")
    sort_by_priority: bool = Field(True, description="按优先级/版本/日期排序")
    max_answers: int | None = Field(
        None, ge=1, le=20, description="最多返回条数（默认等于 top_k）"
    )

class SearchResult(BaseModel):
    id: str = ""
    question: str
    answer: str
    score: float
    document: str
    priority: int | None = None
    version: int | None = None
    date: str | None = None

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_in_db: int

class CountResponse(BaseModel):
    status: str
    total_records: int
    active_records: int
    collection: str

class HealthResponse(BaseModel):
    status: str
    service: str
    records: int
    active_records: int

class SoftDeleteRequest(BaseModel):
    """软删除知识条目（工单删除时由 Java 调用）"""
    id: str | None = Field(default=None, description="知识库条目 ID，如 kb_ticket_42")
    ticket_id: int | str | None = Field(default=None, description="工单 ID，将定位 kb_ticket_{id}")

class SoftDeleteResponse(BaseModel):
    success: bool
    id: str | None = None
    message: str
    already_inactive: bool = False

class RAGRequest(BaseModel):
    """RAG问答请求"""
    query: str = Field(..., description="用户问题", min_length=1)
    top_k: int = Field(5, ge=1, le=10, description="检索知识条数")
    stream: bool = Field(True, description="是否流式返回")

class RAGResponse(BaseModel):
    """RAG问答响应（非流式）"""
    answer: str
    sources: list[SearchResult]
    has_answer: bool

# ─────────────── FastAPI 应用 ───────────────

app = FastAPI(
    title="运维知识库服务",
    description="OPS Knowledge Base Service - 向量存储与检索",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────── API 端点 ───────────────

@app.get("/api/kb/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="ok",
        service="运维知识库服务",
        records=store.count(),
        active_records=store.count_active(),
    )

@app.get("/api/kb/count", response_model=CountResponse)
async def get_count():
    """查看知识库总条数"""
    return CountResponse(
        status="ok",
        total_records=store.count(),
        active_records=store.count_active(),
        collection="ops_knowledge"
    )

@app.post("/api/kb/add", response_model=AddKnowledgeResponse)
async def add_knowledge(req: AddKnowledgeRequest):
    """
    添加 Q&A 对到知识库
    此接口由 Java 后端（TicketController.resolve()）调用
    实现"处理完成后再自动完善知识库"的反馈闭环

    去重逻辑：相似度 ≥ 阈值时，答案相同则跳过；答案矛盾则按 priority 覆盖或保留旧条
    """
    try:
        result = store.add(
            question=req.question,
            answer=req.answer,
            metadata=req.metadata,
            dedup=req.skip_if_duplicate,
            dedup_threshold=req.dedup_threshold,
            handle_conflicts=req.handle_conflicts,
            conflict_threshold=req.conflict_threshold,
        )
        return AddKnowledgeResponse(
            success=True,
            id=result["id"],
            message=result["message"],
            duplicate=result.get("duplicate", False),
            conflict=result.get("conflict", False),
            action=result.get("action", "added"),
            score=result.get("score"),
            existing_question=result.get("existing_question"),
            superseded_ids=result.get("superseded_ids") or [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"入库失败: {str(e)}")

@app.post("/api/kb/search", response_model=SearchResponse)
async def search_knowledge(req: SearchRequest):
    """检索知识库（相似度 ≥0.60 过滤后，按 priority → version → date → 相似度排序）"""
    try:
        results = store.search(
            query=req.query,
            top_k=req.top_k,
            sort_by_priority=req.sort_by_priority,
            max_answers=req.max_answers,
        )
        return SearchResponse(
            query=req.query,
            results=[SearchResult(**r) for r in results],
            total_in_db=store.count()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

@app.post("/api/kb/soft-delete", response_model=SoftDeleteResponse)
async def soft_delete_knowledge(req: SoftDeleteRequest):
    """
    软删除知识条目（标记 active=false，检索时自动忽略）
    工单删除时由 Java TicketController 调用
    """
    if not req.id and req.ticket_id is None:
        raise HTTPException(status_code=400, detail="必须提供 id 或 ticket_id")
    try:
        result = store.soft_delete(doc_id=req.id, ticket_id=req.ticket_id)
        return SoftDeleteResponse(
            success=result["success"],
            id=result.get("id"),
            message=result["message"],
            already_inactive=result.get("already_inactive", False),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"软删除失败: {str(e)}")

@app.post("/api/rag")
async def rag_chat(req: RAGRequest):
    """
    RAG智能问答核心接口

    工作流程：
    1. 从FAISS检索相关知识
    2. 构建增强Prompt
    3. 调用本地大模型生成答案
    4. 流式或非流式返回

    注意：当前使用模拟回答，实际部署时应集成Ollama/DeepSeek等大模型
    """
    try:
        # Step 1: 检索相关知识
        results = store.search(
            query=req.query,
            top_k=max(req.top_k, MAX_ANSWERS_PER_QUERY),
            sort_by_priority=True,
            max_answers=MAX_ANSWERS_PER_QUERY,
        )

        if not results:
            # 知识库中没有任何相关内容
            answer = "抱歉，知识库中没有找到相关信息。建议您转人工处理，我们的运维专家会尽快为您解答。"
            return RAGResponse(
                answer=answer,
                sources=[],
                has_answer=False
            )

        # Step 2: 过滤低质量结果（相似度 < 0.60）
        relevant_results = [r for r in results if r['score'] >= 0.60]

        if not relevant_results:
            answer = f"我找到了一些可能相关的信息，但匹配度不高。\n\n{results[0]['question']}\n{results[0]['answer']}\n\n如果这不能解决您的问题，建议转人工处理。"
            return RAGResponse(
                answer=answer,
                sources=[SearchResult(**r) for r in results[:2]],
                has_answer=False
            )

        # Step 3: 构建RAG Prompt
        context = "\n\n".join([
            f"参考资料{i+1}（相似度{r['score']:.0%}）:\n问题: {r['question']}\n答案: {r['answer']}"
            for i, r in enumerate(relevant_results[:3])
        ])

        system_prompt = """你是一个专业的运维助手，基于提供的知识库资料回答用户问题。

要求：
1. 严格基于提供的参考资料回答，不要编造信息
2. 如果资料不足以回答问题，明确说明"根据现有资料无法完全回答"
3. 回答要清晰、结构化，使用Markdown格式
4. 如果涉及操作步骤，使用编号列表
5. 回答长度控制在200-500字之间

"""

        user_prompt = f"""{system_prompt}

{context}

用户问题：{req.query}

请基于上述参考资料给出专业回答："""

        # Step 4: 调用大模型生成答案
        # TODO: 实际部署时替换为真实的LLM调用
        # 示例：使用Ollama API
        # answer = await call_ollama(user_prompt)

        # 当前使用模拟回答（基于检索结果组合）
        answer = generate_mock_answer(req.query, relevant_results)

        if req.stream:
            # 流式返回（模拟逐字输出效果）
            return StreamingResponse(
                stream_answer(answer),
                media_type="text/event-stream"
            )
        else:
            # 非流式返回
            return RAGResponse(
                answer=answer,
                sources=[SearchResult(**r) for r in relevant_results[:3]],
                has_answer=True
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG问答失败: {str(e)}")


async def stream_answer(answer: str):
    """
    模拟流式输出答案
    实际部署时应该从LLM的stream接口逐字读取
    """
    words = answer.split()
    for word in words:
        yield f"data: {word}\n\n"
        await asyncio.sleep(0.05)  # 模拟打字效果
    yield "data: [DONE]\n\n"


def generate_mock_answer(query: str, results: list) -> str:
    """按优先级排序后，最多展示三条参考答案"""
    if len(results) == 0:
        return "抱歉，没有找到相关知识。建议您转人工处理，我们的运维专家会尽快为您解答。"

    top_results = results[:MAX_ANSWERS_PER_QUERY]

    if top_results[0]["score"] < 0.65:
        best = top_results[0]
        return (
            f"知识库中有一些可能相关的信息，但匹配度不高。\n\n"
            f"**相关参考：**\n{best['question']}\n{best['answer'][:200]}...\n\n"
            f"如果这不能解决您的问题，建议转人工处理。"
        )

    lines = ["根据知识库检索结果（按优先级从高到低），供您参考：\n"]
    for i, r in enumerate(top_results, 1):
        prio = r.get("priority", "—")
        ver = r.get("version")
        date = r.get("date")
        tag_parts = [f"priority={prio}"]
        if ver is not None:
            tag_parts.append(f"v={ver}")
        if date:
            tag_parts.append(f"date={date}")
        tag = ", ".join(tag_parts)
        lines.append(
            f"### 参考 {i}（{tag}，相似度 {r['score']:.0%}）\n\n"
            f"**{r['question']}**\n\n{r['answer']}\n"
        )

    lines.append(
        "\n---\n*以上信息来自运维知识库，如未能解决您的问题，请点击「转人工」。*"
    )
    return "\n".join(lines)


# 在文件顶部添加导入
import asyncio

# ─────────────── 启动入口 ───────────────

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 运维知识库服务启动中...")
    print(f"   引擎: ChromaDB + BGE-M3")
    print(f"   端口: 8000")
    print(f"   健康检查: http://localhost:8000/api/kb/health")
    print(f"   RAG问答: http://localhost:8000/api/rag")
    print(f"   知识库条数: {store.count()}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
