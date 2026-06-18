from fastapi import FastAPI
from pydantic import BaseModel
from rag_ops import get_answer  # 导入你写好的问答函数

app = FastAPI(title="运维数字员工 API", version="1.0")

# 定义请求体格式
class QuestionRequest(BaseModel):
    question: str

# 定义响应体格式
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

# 可选：添加一个健康检查接口
@app.get("/health")
def health():
    return {"status": "running"}