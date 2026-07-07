from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os
from langchain_tavily import TavilySearch
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from langchain.agents import create_agent
from langchain.messages import HumanMessage,SystemMessage,AIMessage,AIMessageChunk
from langchain_core.runnables import RunnableConfig

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
# 3.2 setup checkpointer
conn_string = os.getenv("CONN_STR")
if conn_string:
    pool = ConnectionPool(conninfo=conn_string)
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # 自动创建 checkpoint 表，首次运行执行一次即可
else:
    print("警告：未配置数据库连接串，会话记忆不会持久化")

agent = create_agent(
    model=model,
    tools=[web_search],
    system_prompt=system_prompt,
    checkpointer=checkpointer
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
    try:
        if not image or image.strip() == "":# if not image
            message = HumanMessage([{"type":"text","text":prompt}])
        else: # if exist image
            message = HumanMessage([{"type":"image","image":image}])

        for chunk,metadata in agent.stream(
            {"messages":[message]},
                config=RunnableConfig(
                    configurable={"thread_id": thread_id},
                    recursion_limit=50,  # 可选：放大Agent递归调用上限，避免多轮工具调用时报错
                    # tags=["chef_agent"],  # 可选：打标签用于日志过滤
                    # metadata={"scene": "recipe"}  # 可选：附加元数据
                    ),
                stream_mode="messages"
        ):
            if isinstance(chunk,AIMessageChunk) and chunk.content:
                yield chunk.content
    except Exception as err:
        yield "流式输出错误"

async def get_history(thread_id: str)->list[dict[str,str]]:
    """
    Args:
    :param thread_id:
    :return:
    """
    # according to the thread_id by user provided
    cp = checkpointer.get({"configurable":{"thread_id":thread_id}})
    if not cp:
        print("invalid thread_id")
        return []
    channel_values = cp.get("channel_values")
    if not channel_values:
        return []
    messages = channel_values.get("messages", [])
    if not messages:
        return []
    result = []
    for message in messages:
        if not message.content:
            continue

        if isinstance(message,HumanMessage):
            result.append({"role":"user","content":message.content})
        elif isinstance(message,AIMessage):
            result.append({"role":"assistance","content":message.content})
        else:
            print("没获取到用户和AI的对话消息")
    return result

async def clear_history(thread_id: str):
    checkpointer.delete_thread(thread_id)