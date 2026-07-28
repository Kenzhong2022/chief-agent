from fastapi import APIRouter, Query
from src.services.suggest_index import load_index

router = APIRouter()

# 服务启动时加载索引（在 main.py 的 lifespan 中可调用）
PREFIX_INDEX = None

def init_index():
    global PREFIX_INDEX
    PREFIX_INDEX = load_index()
    print(f"✅ 联想词索引加载完成，共 {len(PREFIX_INDEX)} 个前缀")

@router.get("/suggest")
async def suggest(q: str = Query(..., min_length=1, description="用户输入前缀")):
    if PREFIX_INDEX is None:
        return {"suggestions": []}
    candidates = PREFIX_INDEX.get(q, [])[:10]
    return {"query": q, "suggestions": candidates}