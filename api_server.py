import asyncio
from functools import partial
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag_ops import get_answer  # 导入您写好的问答函数

app = FastAPI(title="运维数字员工 API", version="1.0")

# 1. 启用 CORS 跨域支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 生产环境建议限制具体前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 路由 1：兼容原有的 /ask 接口 ----
class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    success: bool
    answer: str
    need_human: bool
    sources: list = []

@app.post("/ask", response_model=AnswerResponse)
def ask_endpoint(request: QuestionRequest):
    result = get_answer(request.question)
    return AnswerResponse(
        success=result["success"],
        answer=result["answer"],
        need_human=result["need_human"],
        sources=result.get("sources") or [],
    )


# ---- 路由 2：对接 Java ChatController 的流式接口 ----
class HistoryMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    query: str
    history: list[HistoryMessage] = []

@app.post("/api/rag")
async def rag_endpoint(request: QueryRequest):
    # 使用 run_in_executor 避免同步的 get_answer 阻塞 FastAPI 异步主线程
    loop = asyncio.get_event_loop()
    history = [{"role": m.role, "content": m.content} for m in request.history]
    result = await loop.run_in_executor(
        None, partial(get_answer, request.query, history if history else None)
    )
    
    answer = result.get("answer", "")
    need_human = result.get("need_human", False)
    
    # 核心飞轮：如果底层判定需要转人工，但文本中没有包含 Java 检查的触发词
    # 我们在这里主动追加，让 Java 端顺利触发工单保存
    if need_human and not any(kw in answer for kw in ["无法回答", "抱歉", "人工"]):
        answer += "\n（抱歉，该问题超出我的知识范围，系统无法回答，已为您自动转接人工服务。）"
        
    async def event_generator():
        # 按行推送，保留换行（2 字切片会把 \n  trim 掉导致 Markdown 粘成一行）
        for line in answer.split("\n"):
            yield f"data: {line}\n\n"
            await asyncio.sleep(0.02)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# 健康检查
@app.get("/health")
def health():
    return {"status": "running"}