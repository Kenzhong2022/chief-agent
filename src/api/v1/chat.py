from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from fastapi import Request  # 用于获取请求头
from src.models.schemas import ChatRequest,StopStreamRequest
from src.agents.chief_agent import search_recipes,get_history,clear_history,save_snapshot
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
            print(f"[中断] thread_id={thread_id}, 客户端断开 (CancelledError/GeneratorExit)")
            return

        except BrokenPipeError as e:
            # 捕获写入管道错误（通常由客户端断开引起）
            print(f"[中断] thread_id={thread_id}, 连接断开 (BrokenPipeError): {e}")
            return

        except Exception as e:
            print(f"[错误] thread_id={thread_id}, 发生异常: {type(e).__name__}: {e}")
            yield {"data": f"内部错误: {e}", "retry": 30000}

        except BaseException as e:
            # 兜底：捕获所有其他异常（包括 SystemExit、KeyboardInterrupt 等）
            print(f"[严重] thread_id={thread_id}, 未捕获的异常: {type(e).__name__}: {e}")
            # 不能 yield，因为连接可能已断，直接退出
            return

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

@router.post("/chat/stop")
async def stop_stream(request: StopStreamRequest):
    """
    停止生成并保存快照。
    前端在断开 SSE 后调用此接口，传入 thread_id 和 last_event_id。
    """
    thread_id = request.thread_id
    last_event_id = request.last_event_id

    # 调用服务层函数保存快照（内部会先取消任务）
    success, msg = await save_snapshot(thread_id, last_event_id)

    return {
        "success": success,
        "msg": msg,
        "data": {"thread_id": thread_id, "last_event_id": last_event_id} if success else None
    }