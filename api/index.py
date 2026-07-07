from mangum import Mangum
from src.main import app  # 路径统一，本地+云端都能识别
handler = Mangum(app)