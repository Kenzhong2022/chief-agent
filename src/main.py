from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# 关键修改：app → src
from src.api.v1.chat import router as chat_router

app = FastAPI(title="私人厨师Agent服务")

# 跨域中间件（前端调试必备，否则浏览器跨域报错）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载聊天路由，统一前缀 /api/v1
app.include_router(chat_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    # 此处同步修改为 src.main:app
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)