from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """
    聊天请求体：接收用户的食材文本、图片、会话ID
    """
    # 必填：必须传 prompt，不传直接报错
    prompt: str = Field(..., min_length=1, description="用户输入的文本指令/食材清单")
    image: str | None = Field(None, description="食材图片URL/base64，无图片则不传")
    thread_id: str = Field(..., min_length=1, description="会话唯一线程ID，用于持久化记忆")

class StopStreamRequest(BaseModel):
    """
    停止生成并保存快照请求体：接收会话ID和最后收到的事件ID
    """
    # 必填：会话线程ID，用于定位缓存和检查点
    thread_id: str = Field(..., min_length=1, description="会话唯一线程ID")
    # 必填：前端最后成功接收到的SSE事件ID，用于标记断点位置
    last_event_id: str = Field(..., min_length=1, description="最后收到的SSE事件ID，用于续传")