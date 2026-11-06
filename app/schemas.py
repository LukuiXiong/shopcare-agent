# Pydantic 用于定义接口的数据格式，并自动校验用户输入
from uuid import UUID
from pydantic import BaseModel, Field


# POST /chat 的请求体，例如 {"message": "你好"}
class ChatRequest(BaseModel):
    # 限制消息长度，避免空消息或过长输入
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=2000)


# POST /chat 的响应体，reply 保存模型返回的文字
class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
