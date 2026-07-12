import traceback
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os
from langchain_tavily import TavilySearch
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from psycopg_pool import ConnectionPool
from langchain.agents import create_agent
from langchain.messages import HumanMessage,SystemMessage,AIMessage,AIMessageChunk
from langchain_core.runnables import RunnableConfig
from urllib.parse import urlparse
from src.cache import stream_cache
import asyncio
from typing import Dict
from langgraph.pregel import Pregel

load_dotenv() # import environment key value

from langchain.tools import tool
# 1.create model
model = init_chat_model(
    model="qwen3.5-plus",
    model_provider="openai",
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY")
)
# 2.def tool
# search_tool
web_search = TavilySearch(
    max_results=5,
    topic="general",
)
# 3.create agent
# 3.1 system prompt
system_prompt = """
你是一名私人厨师。收到用户提供的食材照片或清单后，请按以下流程操作：
1.识别和评估食材：若用户提供照片，首先辨识所有可见食材。基于食材的外观状态，评估其新鲜度与可用量，整理出一份“当前可用食材清单”。
2.智能食谱检索：优先调用 web_search 工具，以“可用食材清单”为核心关键词，查找可行菜谱。
3.多维度评估与排序：从营养价值和制作难度两个维度对检索到的候选食谱进行量化打分，并根据得分排序，制作简单且营养丰富的排名靠前。
4.结构化方案输出：把排序后的食谱整理为一份结构清晰的建议报告，要包含食谱信息、得分、推荐理由、食谱的参考图片，帮助用户快速做出决策。

请严格按照流程，优先调用 web_search 工具搜索食谱，搜索不到的情况下才能自己发挥。
"""
# 类型注解替换为 Pregel
agent: Pregel | None = None
# 全局 checkpointer 引用（将在 build_agent 中赋值）
_checkpointer: AsyncPostgresSaver | None = None
def build_agent(checkpointer):
    """根据 checkpointer 创建 agent 实例"""
    global _checkpointer
    _checkpointer = checkpointer
    return create_agent(
        model=model,
        tools=[web_search],
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )

async def search_recipes(prompt: str, image: str, thread_id: str):
    """流式输出食谱推荐结果，逐块返回文本片段。

    Args:
        prompt: 用户输入的文本指令
        image: 食材图片URL，无图片传 None
        thread_id: 会话线程ID

    Yields:
        逐段生成的食谱文本片段
    """
    current_task = asyncio.current_task()
    if current_task:
        await register_task(thread_id, current_task)

    try:
        # ========== 前置校验：非法参数直接返回，不往下游传递 ==========
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            yield "参数错误：提问内容不能为空"
            return

        if not thread_id or not isinstance(thread_id, str) or not thread_id.strip():
            yield "参数错误：会话ID不能为空"
            return

            # 图片URL非法就自动忽略，降级为纯文本对话，不触发模型400报错
        use_image = _is_valid_image_url(image)
        if image and not use_image:
            print(f"无效图片URL已忽略：{image}")

        # 构造消息，格式严格规范
        content = [{"type": "text", "text": prompt.strip()}]
        if use_image:
            content.append({
                "type": "image_url",
                "image_url": {"url": image.strip()}
            })
        print('content', content)
        message = HumanMessage(content=content)
        # 获取当前最大 ID（从缓存读取）
        cur_id = stream_cache.get_current_max_id(thread_id)

        async for chunk, metadata in agent.astream(
                {"messages": [message]},
                config=RunnableConfig(configurable={"thread_id": thread_id}, recursion_limit=50),
                stream_mode="messages"
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                cur_id += 1
                data = chunk.content
                # 写入缓存（异步加锁）
                await stream_cache.add_chunk(thread_id, cur_id, data)
                # 产出 SSE 事件（字典格式）
                yield {"id": str(cur_id),"event": "message","data": data, "retry": 30000}

    except (asyncio.CancelledError, GeneratorExit):
        print(f"[search_recipes] 大模型生成被中断，当前已生成 {stream_cache.get_current_max_id(thread_id)} 个 token")
        return  # 直接退出，不再向上抛出

    except Exception as err:
        print(f"[search_recipes] 发生错误: {err}")
        traceback.print_exc()  # 添加这一行，会打印完整的调用堆栈
        yield {"data": f"生成失败: {err}"}
        return
    finally:
        await unregister_task(thread_id)

async def get_history(thread_id: str) -> list[dict[str, str]]:
    config = RunnableConfig(configurable={"thread_id": thread_id})
    # 获取最新状态快照
    snapshot = await agent.aget_state(config)
    if not snapshot or not snapshot.values:
        print("invalid thread_id")
        return []
    # 提取当前会话最新 checkpoint_id
    latest_checkpoint_id = snapshot.config["configurable"]["checkpoint_id"]
    print("会话最新 checkpoint_id:", latest_checkpoint_id)

    messages = snapshot.values.get("messages", [])
    result = []
    for message in messages:
        if not message.content:
            continue
        if isinstance(message, HumanMessage):
            result.append({"role": "user", "content": message.content})
        elif isinstance(message, AIMessage):
            result.append({"role": "assistant", "content": message.content})
    return result

async def clear_history(thread_id: str) -> tuple[bool, str]:
    checkpointer = _checkpointer
    if not checkpointer or not agent:
        return False, "服务未初始化"

    try:
        # 删除数据库会话
        await checkpointer.adelete_thread(thread_id)
        # 清空分片缓存
        await stream_cache.clear_thread(thread_id)
        return True, "会话已清空"
    except Exception as e:
        traceback.print_exc()
        return False, f"清理失败: {str(e)}"

async def save_snapshot(thread_id: str, last_event_id: str) -> tuple[bool, str]:
    """
    将缓存中的半截内容保存到检查点，并标记为未完成。
    返回 (是否成功, 消息)
    """
    # 1. 先尝试取消任务 即使任务已经结束
    await cancel_task(thread_id)

    # 2. 从 Redis/内存缓存中获取所有已生成的文本（按顺序拼接）
    chunks = await stream_cache.get_chunks(thread_id, 1)   # 获取全部（ID>=1）
    if not chunks:
        return False, "没有可保存的内容，可能生成尚未开始或缓存已清空"
    print(chunks)
    full_text = "".join(data for _, data in chunks)

    # 3. 构造“未完成”的 AI 消息，存储 last_event_id 和完成标记
    partial_msg = AIMessage(
        content=full_text,
        additional_kwargs={
            "last_event_id": last_event_id,
            "is_complete": False,
        }
    )

    # 4. 更新 LangGraph 检查点
    config:RunnableConfig = {"configurable": {"thread_id": thread_id}}
    # 获取当前状态
    state = await agent.aget_state(config)
    messages = state.values.get("messages", []) if state and state.values else []

    # 如果最后一条消息是 AI 消息且未完成，则替换；否则追加
    if messages and isinstance(messages[-1], AIMessage) and not messages[-1].additional_kwargs.get("is_complete", True):
        messages[-1] = partial_msg
    else:
        messages.append(partial_msg)

    # 更新状态
    await agent.aupdate_state(config, {"messages": messages})

    # 5. 可选：清理缓存（如果决定保存后即清理，可以启用）
    await stream_cache.clear_thread(thread_id)

    return True, "快照已保存"

# ========== 新增1：极简URL校验函数，2行代码解决图片URL非法导致的400报错 ==========
def _is_valid_image_url(url: str) -> bool | str:
    """只校验最核心的两点：有http/https协议、有公网域名，过滤本地/内网地址"""
    if not url or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
        return (
            parsed.scheme in ("http", "https")
            and parsed.netloc
            and not parsed.netloc.startswith(("127.", "localhost", "192.168.", "10."))
        )
    except Exception:
        return False

active_tasks:Dict[str, asyncio.Task] = {}
task_lock = asyncio.Lock()

async def register_task(thread_id: str, task: asyncio.Task):
    """注册任务到全局字典"""
    async with task_lock:
        active_tasks[thread_id] = task
        print(f"[TaskManager] ✅ 注册任务 | thread_id: {thread_id} | task_id: {id(task)}")

async def unregister_task(thread_id: str):
    """从全局字典中移除任务"""
    async with task_lock:
        task = active_tasks.pop(thread_id, None)
        if task:
            print(f"[TaskManager] ❌ 注销任务 | thread_id: {thread_id} | task_id: {id(task)} (成功)")
        else:
            print(f"[TaskManager] ⚠️ 注销任务 | thread_id: {thread_id} (未找到任务)")

async def cancel_task(thread_id: str) -> bool:
    """
    取消指定 thread_id 的任务
    返回 True 表示成功取消，False 表示任务不存在或已完成
    """
    async with task_lock:
        task = active_tasks.get(thread_id)
        if task is not None and not task.done():
            task.cancel()
            print(f"[TaskManager] 🛑 取消任务 | thread_id: {thread_id} | task_id: {id(task)} (成功)")
            return True
        else:
            if task is None:
                status = "任务不存在"
            else:
                status = f"任务已完成 (done={task.done()})"
            print(f"[TaskManager] ⚠️ 取消任务 | thread_id: {thread_id} | {status}")
            return False