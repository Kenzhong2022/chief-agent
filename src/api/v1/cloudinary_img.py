import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, UploadFile, HTTPException
import os
import io

# 传统方式读取环境变量
cloudinary_url = os.getenv("CLOUDINARY_URL")
if not cloudinary_url:
    raise RuntimeError("未读取到 CLOUDINARY_URL，请检查 .env 文件")

cloudinary.config(cloudinary_url=cloudinary_url)
cfg = cloudinary.config()

if not cfg.cloud_name or not cfg.api_key or not cfg.api_secret:
    raise RuntimeError("CLOUDINARY_URL 格式错误，密钥信息不完整")

router = APIRouter(prefix="/cloudinary_img", tags=["后端直传云存储"])
FIXED_USER_ID = 1
FOLDER = f"chat_upload/{FIXED_USER_ID}"
MAX_SIZE = 5 * 1024 * 1024
ALLOW_MIME = {"image/jpeg", "image/png", "image/webp"}


@router.post("/upload")
async def backend_upload(file: UploadFile):
    print(f"收到文件：{file.filename}，大小：{len(await file.read()) / 1024:.2f}KB")
    # 重置文件游标，刚才read读完了
    await file.seek(0)
    content = await file.read()

    if file.content_type not in ALLOW_MIME:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp")
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="文件不能超过5MB")

    try:
        file_stream = io.BytesIO(content)
        upload_result = cloudinary.uploader.upload(
            file_stream,
            folder=FOLDER,
            resource_type="image"
        )
        print(f"上传成功 | URL: {upload_result['secure_url']}")
        return {
            "url": upload_result["secure_url"],
            "public_id": upload_result["public_id"]
        }
    except Exception as err:
        print(f"上传失败 | 错误：{str(err)}")
        raise HTTPException(status_code=500, detail=f"云存储上传失败：{str(err)}")


@router.post("/upload-batch")
async def backend_batch_upload(files: list[UploadFile]):
    print(f"批量上传，共 {len(files)} 个文件")
    url_list = []
    for file in files:
        res = await backend_upload(file)
        url_list.append(res["url"])
    print(f"批量上传完成，链接列表：{url_list}")
    return {"urls": url_list}