# src/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# 导入路由
from src.api.v1.chat import router as chat_router
from src.api.v1.cloudinary_img import router as cloudinary_router

# 导入 chief_agent 模块，以便重新设置 agent
from src.agents import chief_agent,suggest_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    conn_string = os.getenv("CONN_STR")
    pool = None
    if conn_string:
        # open=False：构造时不自动开连接，消除RuntimeWarning
        pool = AsyncConnectionPool(conninfo=conn_string, open=False)
        await pool.open()
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        chief_agent.agent = chief_agent.build_agent(checkpointer)
        app.state.pool = pool
        print("✅ PostgreSQL 检查点初始化成功")
    else:
        print("⚠️ 未配置 CONN_STR，使用无状态模式")
        chief_agent.agent = chief_agent.build_agent(None)
        # 初始化搜索联想 agent（这里假设无需 checkpointer，传 None）
        suggest_agent.agent = suggest_agent.build_agent(checkpointer=None)

    # 服务运行全程持有连接池，不提前销毁
    yield

    # 服务关闭时统一释放资源
    if pool is not None:
        await pool.close()
        print("✅ PostgreSQL 连接池已正常关闭")
app = FastAPI(title="私人厨师Agent服务", lifespan=lifespan)

# 跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/v1")
app.include_router(cloudinary_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)