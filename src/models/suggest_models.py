from pydantic import BaseModel, Field
from typing import List

class SuggestWord(BaseModel):
    word: str = Field(description="清洗后的联想词，如'苹果手机'")
    type: str = Field(description="词类型：品牌/型号/品类/属性")
    score: float = Field(description="推荐优先级，0~1")

class CleanedProducts(BaseModel):
    total_suggestions: int = Field(description="生成的联想词总数（去重后）")
    suggestions: List[SuggestWord] = Field(description="清洗后的联想词列表，已去重")