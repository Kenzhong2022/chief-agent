from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """
    聊天请求体：接收用户的食材文本、图片、会话ID
    """
    # 必填：必须传 prompt，不传直接报错
    prompt: str = Field(..., min_length=1, description="用户输入的文本指令/食材清单")
    image: str | None = Field(None, description="食材图片URL/base64，无图片则不传")
    thread_id: str = Field(..., min_length=1, description="会话唯一线程ID，用于持久化记忆")