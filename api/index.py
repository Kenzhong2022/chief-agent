from mangum import Mangum
from app.main import app

# 将 FastAPI 应用包装为 Vercel 兼容的 Serverless 函数
handler = Mangum(app)