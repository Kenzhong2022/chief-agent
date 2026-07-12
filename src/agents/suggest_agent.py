# src/agents/suggest_agent.py
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from src.tools.suggest_tools import get_raw_product_names  # 你的工具
from src.models.suggest_models import CleanedProducts  # Pydantic 输出模型

agent = None  # 模块级变量，由 lifespan 注入


def build_agent(checkpointer=None):
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    # 绑定结构化输出（核心：确保返回格式固定）
    llm_with_structure = llm.with_structured_output(CleanedProducts)

    tools = [get_raw_product_names]

    # 用 LangGraph 的 create_react_agent 快速搭建
    # 也可手动构建 StateGraph，按需
    agent_executor = create_react_agent(
        model="deepseek-",
        tools=tools,
        checkpointer=checkpointer,  # 若无状态可传 None
        prompt="你是一个电商搜索词清洗专家。从原始商品标题中提取高质量联想词。"
    )
    return agent_executor