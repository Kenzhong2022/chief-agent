from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 导入两类路由
from src.api.v1.chat import router as chat_router
from src.api.v1.cloudinary_img import router as cloudinary_router

app = FastAPI(title="私人厨师Agent服务")

# 跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一挂载全部接口，前缀 /api/v1
app.include_router(chat_router, prefix="/api/v1")
app.include_router(cloudinary_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)