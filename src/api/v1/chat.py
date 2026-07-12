from fastapi import APIRouter
from fastapi.responses import StreamingResponse  # 流式响应核心类
from sse_starlette.sse import EventSourceResponse
from fastapi import Request  # 用于获取请求头
from src.models.schemas import ChatRequest
from src.agents.chief_agent import search_recipes,get_history,clear_history
from src.cache import stream_cache
import asyncio
router = APIRouter()

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    thread_id = request.thread_id
    last_id = req.headers.get("last-event-id")  # 用于断点续传（如有）
    start_id = int(last_id) + 1 if last_id else 1

    async def event_generator():
        try:
            # 重放已有缓存中未发送的部分（异步获取）
            cached = await stream_cache.get_chunks(thread_id, start_id)
            for cid, data in cached:
                yield {"id": str(cid),"event": "message", "data": data, "retry": 30000}

            # 继续生成新内容
            async for event in search_recipes(request.prompt, request.image, thread_id):
                yield event

            # ========== 流式完整正常结束，清理缓存 ==========
            await stream_cache.clear_thread(thread_id)

        except (asyncio.CancelledError, GeneratorExit):
            # 客户端断开连接，停止生成
            print(f"客户端已断开连接，停止生成 (thread: {thread_id})")
            # 可在这里做清理工作
            return
        except Exception as e:
            print(f"生成器异常: {e}")
            yield {"data": f"内部错误: {e}", "retry": 30000}

    return EventSourceResponse(
        event_generator(),
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