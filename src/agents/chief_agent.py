from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os
from langchain_tavily import TavilySearch
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool, PoolTimeout
from psycopg import OperationalError
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AIMessageChunk
from langchain_core.runnables import RunnableConfig
from typing import AsyncGenerator, Optional

load_dotenv()

# 全局变量：连接池、checkpointer、连接串
CONN_STRING = os.getenv("CONN_STR")
pool: Optional[ConnectionPool] = None
checkpointer: Optional[PostgresSaver] = None

# 1. 大模型&工具全局单例（无数据库依赖，可常驻）
model = init_chat_model(
    model="qwen3.5-plus",
    model_provider="openai",
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY")
)
web_search = TavilySearch(max_results=5, topic="general")
system_prompt = """
你是一名私人厨师。收到用户提供的食材照片或清单后，请按以下流程操作：
1.识别和评估食材：若用户提供照片，首先辨识所有可见食材。基于食材的外观状态，评估其新鲜度与可用量，整理出一份“当前可用食材清单”。
2.智能食谱检索：优先调用 web_search 工具，以“可用食材清单”为核心关键词，查找可行菜谱。
3.多维度评估与排序：从营养价值和制作难度两个维度对检索到的候选食谱进行量化打分，并根据得分排序，制作简单且营养丰富的排名靠前。
4.结构化方案输出：把排序后的食谱整理为一份结构清晰的建议报告，要包含食谱信息、得分、推荐理由、食谱的参考图片，帮助用户快速做出决策。

请严格按照流程，优先调用 web_search 工具搜索食谱，搜索不到的情况下才能自己发挥。
"""

# ===================== 核心：全局连接池管理函数 =====================
def init_pool() -> None:
    """创建/重建连接池，配置防断开参数"""
    global pool, checkpointer
    if not CONN_STRING:
        raise RuntimeError("未配置 CONN_STR 环境变量")

    # 适配Serverless的池参数，关键配置
    new_pool = ConnectionPool(
        conninfo=CONN_STRING,
        min_size=1,        # 最小常驻1条连接
        max_size=2,         # 限制最大连接数，避免Vercel多实例爆连接
        max_wait=2000,      # 获取连接超时2秒
        max_idle=180,       # 闲置180秒自动回收，防止PG断开标记为BAD
        max_lifetime=600,   # 连接最长存活10分钟，强制轮换
    )
    # 预校验连接可用
    try:
        with new_pool.connection() as conn:
            conn.execute("SELECT 1;")
    except (OperationalError, PoolTimeout):
        new_pool.close()
        raise RuntimeError("数据库连接初始化失败")

    # 销毁旧池（如果存在失效旧池）
    if pool is not None:
        try:
            pool.close()
        except Exception:
            pass
    # 替换全局池
    pool = new_pool
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()

def get_healthy_checkpointer() -> PostgresSaver:
    """获取可用checkpointer，连接失效自动重建连接池"""
    global pool, checkpointer
    # 池未初始化，先创建
    if pool is None or checkpointer is None:
        init_pool()

    # 校验现有池连接是否失效
    try:
        with pool.connection() as conn:
            conn.execute("SELECT 1;")
        return checkpointer
    except (OperationalError, PoolTimeout):
        # 连接损坏，重建全新连接池
        init_pool()
        return checkpointer

# ===================== 业务接口（使用get_healthy_checkpointer自动修复坏连接） =====================
async def search_recipes(prompt: str, image: str, thread_id: str) -> AsyncGenerator[str, None]:
    try:
        # 自动拿到健康可用的checkpointer，坏连接会自动重建池
        cp = get_healthy_checkpointer()
        agent = create_agent(
            model=model,
            tools=[web_search],
            system_prompt=system_prompt,
            checkpointer=cp
        )
        if not image or image.strip() == "":
            message = HumanMessage([{"type":"text","text":prompt}])
        else:
            message = HumanMessage([{"type":"image_url","image_url": image}])

        for chunk,metadata in agent.stream(
            {"messages":[message]},
            config=RunnableConfig(
                configurable={"thread_id": thread_id},
                recursion_limit=50,
            ),
            stream_mode="messages"
        ):
            if isinstance(chunk,AIMessageChunk) and chunk.content:
                yield chunk.content
    except Exception as err:
        print(f"流式错误: {err}")
        yield "流式输出错误"

async def get_history(thread_id: str)->list[dict[str,str]]:
    try:
        cp = get_healthy_checkpointer()
        config = {"configurable":{"thread_id":thread_id}}
        cp_state = cp.get(config)
        if not cp_state:
            print("invalid thread_id")
            return []
        channel_values = cp_state.get("channel_values", {})
        messages = channel_values.get("messages", [])
        result = []
        for msg in messages:
            if not msg.content:
                continue
            if isinstance(msg, HumanMessage):
                result.append({"role":"user","content":msg.content})
            elif isinstance(msg, AIMessage):
                # 修复原代码拼写错误 assistance → assistant
                result.append({"role":"assistant","content":msg.content})
        return result
    except Exception as e:
        print(f"获取历史异常: {e}")
        return []

async def clear_history(thread_id: str):
    try:
        cp = get_healthy_checkpointer()
        cp.delete_thread({"configurable":{"thread_id": thread_id}})
    except Exception as e:
        print(f"清空会话异常: {e}")