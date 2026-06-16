"""
运维知识库服务 - FastAPI
暴露接口：
  POST /api/kb/add    - 添加 Q&A 对到知识库（Java 后端调用）
  GET  /api/kb/search - 检索知识库（调试用）
  GET  /api/kb/count  - 查看知识库条数
  GET  /api/kb/health - 健康检查
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from chroma_store import store
import uvicorn

# ─────────────── 数据模型 ───────────────

class AddKnowledgeRequest(BaseModel):
    """Java 后端调用 /api/kb/add 时的请求体"""
    question: str = Field(..., description="用户原始问题", min_length=1)
    answer: str = Field(..., description="人工修正后的正确答案", min_length=1)
    skip_if_duplicate: bool = Field(default=True, description="是否开启语义去重（默认开启）")
    dedup_threshold: float = Field(default=0.90, ge=0.5, le=1.0, description="去重相似度阈值")

class AddKnowledgeResponse(BaseModel):
    success: bool
    id: str
    message: str
    duplicate: bool = False
    score: float | None = None
    existing_question: str | None = None

class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索查询", min_length=1)
    top_k: int = Field(5, ge=1, le=20, description="返回条数")

class SearchResult(BaseModel):
    id: str = ""
    question: str
    answer: str
    score: float
    document: str

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_in_db: int

class CountResponse(BaseModel):
    status: str
    total_records: int
    collection: str

class HealthResponse(BaseModel):
    status: str
    service: str
    records: int

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
        records=store.count()
    )

@app.get("/api/kb/count", response_model=CountResponse)
async def get_count():
    """查看知识库总条数"""
    return CountResponse(
        status="ok",
        total_records=store.count(),
        collection="ops_knowledge"
    )

@app.post("/api/kb/add", response_model=AddKnowledgeResponse)
async def add_knowledge(req: AddKnowledgeRequest):
    """
    添加 Q&A 对到知识库
    此接口由 Java 后端（TicketController.resolve()）调用
    实现"处理完成后再自动完善知识库"的反馈闭环

    去重逻辑：默认开启，相似度 ≥ 0.90 的已有记录会被跳过
    """
    try:
        result = store.add(
            question=req.question,
            answer=req.answer,
            dedup=req.skip_if_duplicate,
            dedup_threshold=req.dedup_threshold
        )
        return AddKnowledgeResponse(
            success=True,
            id=result["id"],
            message=result["message"],
            duplicate=result.get("duplicate", False),
            score=result.get("score"),
            existing_question=result.get("existing_question")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"入库失败: {str(e)}")

@app.post("/api/kb/search", response_model=SearchResponse)
async def search_knowledge(req: SearchRequest):
    """检索知识库（调试用，也可供成员A联调）"""
    try:
        results = store.search(query=req.query, top_k=req.top_k)
        return SearchResponse(
            query=req.query,
            results=[SearchResult(**r) for r in results],
            total_in_db=store.count()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

# ─────────────── 启动入口 ───────────────

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 运维知识库服务启动中...")
    print(f"   引擎: ChromaDB + BGE-M3")
    print(f"   端口: 8000")
    print(f"   健康检查: http://localhost:8000/api/kb/health")
    print(f"   知识库条数: {store.count()}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
