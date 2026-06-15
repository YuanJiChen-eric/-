import asyncio
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

@app.post("/ask", response_model=AnswerResponse)
def ask_endpoint(request: QuestionRequest):
    result = get_answer(request.question)
    return AnswerResponse(
        success=result["success"],
        answer=result["answer"],
        need_human=result["need_human"]
    )


# ---- 路由 2：对接 Java ChatController 的流式接口 ----
class QueryRequest(BaseModel):
    query: str

@app.post("/api/rag")
async def rag_endpoint(request: QueryRequest):
    # 使用 run_in_executor 避免同步的 get_answer 阻塞 FastAPI 异步主线程
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, get_answer, request.query)
    
    answer = result.get("answer", "")
    need_human = result.get("need_human", False)
    
    # 核心飞轮：如果底层判定需要转人工，但文本中没有包含 Java 检查的触发词
    # 我们在这里主动追加，让 Java 端顺利触发工单保存
    if need_human and not any(kw in answer for kw in ["无法回答", "抱歉", "人工"]):
        answer += "\n（抱歉，该问题超出我的知识范围，系统无法回答，已为您自动转接人工服务。）"
        
    async def event_generator():
        # 将回答切片，模拟打字机的流式输出（SSE 格式：data: xxx\n\n）
        chunk_size = 2  # 每次发送 2 个字符
        for i in range(0, len(answer), chunk_size):
            chunk = answer[i:i+chunk_size]
            yield f"data: {chunk}\n\n"
            await asyncio.sleep(0.03)  # 控制打字机速度（秒）

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# 健康检查
@app.get("/health")
def health():
    return {"status": "running"}