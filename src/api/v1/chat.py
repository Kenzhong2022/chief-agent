from fastapi import APIRouter
from fastapi.responses import StreamingResponse  # 流式响应核心类
from src.models.schemas import ChatRequest
from src.agents.chief_agent import search_recipes,get_history,clear_history
router = APIRouter()

@router.post("/chat/stream")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        search_recipes(request.prompt, request.image, request.thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
        }
    )


@router.get("/chat/messages")
async def get_chat_messages(thread_id: str):
    """获取历史消息"""
    messages = await get_history(thread_id)
    return {
        "messages": messages,
    }


@router.delete("/chat/messages")
async def clear_chat_messages(thread_id: str):
    """清空历史消息"""
    await clear_history(thread_id)
    return {"success": True, "msg": "会话历史已清空"}