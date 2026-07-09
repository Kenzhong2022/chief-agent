import time
import os
import cloudinary.utils
from fastapi import APIRouter

router = APIRouter(prefix="/cloudinary", tags=["云存储上传"])

# 临时固定用户ID，后续加登录鉴权只需要改这里为Depends获取
FIXED_USER_ID = 1

@router.post("/sign", summary="获取图片上传签名（前端直传Cloudinary用，临时固定用户）")
def get_upload_sign():
    # 1. 生成时间戳
    timestamp = int(time.time())
    # 2. 固定用户文件夹 chat_upload/1
    upload_folder = f"chat_upload/{FIXED_USER_ID}"
    # 参与签名的参数（前端上传必须和这里完全一致，否则签名校验失败）
    sign_params = {
        "timestamp": timestamp,
        "folder": upload_folder,
        "resource_type": "image"
    }
    # 3. 用api_secret生成加密签名
    signature = cloudinary.utils.api_sign_request(
        params_to_sign=sign_params,
        api_secret=os.getenv("CLOUD_API_SECRET")
    )
    # 返回前端所需全部公开参数，secret绝不返回
    return {
        "cloud_name": os.getenv("CLOUD_NAME"),
        "api_key": os.getenv("CLOUD_API_KEY"),
        "signature": signature,
        "timestamp": timestamp,
        "folder": upload_folder
    }