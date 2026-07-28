# 导入路由
from src.api.v1.chat import router as chat_router
from src.api.v1.cloudinary_img import router as cloudinary_router
from src.api.v1.suggest import router as suggest_router

# src/main.py
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from apscheduler.schedulers.background import BackgroundScheduler

from src.agents import chief_agent
from src.api.v1.suggest import init_index
from src.services.suggest_index import build_prefix_index, save_index
from src.agents.suggest_agent import build_agent as build_suggest_agent

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

    # ----- 加载初始前缀索引（在线查询使用） -----
    init_index()  # 从 prefix_index.json 加载索引到内存

    # ----- 启动定时更新调度器 -----
    scheduler = BackgroundScheduler()
    # scheduler.add_job(
    #     func=update_index_job,
    #     trigger="cron",
    #     day_of_week="mon",  # 每周一
    #     hour=3,  # 凌晨 3 点
    #     minute=0
    # )
    scheduler.add_job(
        func=update_index_job,
        trigger="interval",
        minutes=1
    )
    scheduler.start()
    print("⏰ 联想词库定时更新已启动（每周一 03:00）")
    # 服务运行全程持有连接池，不提前销毁
    yield

    # 服务关闭时统一释放资源
    scheduler.shutdown()
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
app.include_router(suggest_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)


def update_index_job():
    """定时执行：调用大模型清洗商品名，重构前缀索引，并热加载到内存"""
    print("🚀 [定时任务] 开始更新联想词库...")
    try:
        # 1. 构建无状态的 Agent（不使用 checkpointer）
        agent = build_suggest_agent(checkpointer=None)
        result = agent.invoke({"messages": [("user", "请清洗所有商品的标题，生成全品类搜索联想词")]})
        cleaned = result['structured_response']
        # ✅ 核心保护：如果联想词为空，放弃本次更新
        if not cleaned.suggestions:
            print("⚠️ [定时任务] 本次生成联想词为 0 条，保留当前索引不变，跳过更新")
            return
        # 2. 转换为 {词: 分数} 字典
        word_score_map = {item.word: item.score for item in cleaned.suggestions}
        print(f"   生成联想词 {len(word_score_map)} 条")

        # 3. 构建前缀索引并保存到文件
        new_index = build_prefix_index(word_score_map)
        save_index(new_index)
        print(f"   前缀索引已保存（{len(new_index)} 个前缀）")

        # 4. 热更新全局索引（直接修改 suggest 模块中的 PREFIX_INDEX）
        import src.api.v1.suggest as suggest_module
        suggest_module.PREFIX_INDEX = new_index
        print("✅ [定时任务] 联想词库热更新完成！")
    except Exception as e:
        print(f"❌ [定时任务] 词库更新失败: {e}")