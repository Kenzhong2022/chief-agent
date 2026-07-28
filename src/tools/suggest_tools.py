# src/tools/suggest_tools.py
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import List

class ProductNameInput(BaseModel):
    """Input for fetching raw product titles."""
    category: str = Field(
        default="手机",
        description="商品类目名称，例如：'手机'、'笔记本电脑'、'耳机'"
    )

@tool(args_schema=ProductNameInput)
def get_raw_product_names(category: str = "手机") -> List[str]:
    """获取指定类目的原始商品标题列表，用于后续清洗生成联想词。"""
    mock_data = [
        # iPhone 系列
        "Apple iPhone 15 Pro Max 256GB 暗紫色 5G手机 包邮",
        "Apple iPhone 14 128GB 午夜色 国行正品 全新未拆封",
        "iPhone SE 第三代 A15芯片 64GB 红色 学生党备用机",
        "苹果手机 iPhone 13 Pro 远峰蓝 1TB 官方翻新 原装配件",
        # 华为系列
        "Huawei Mate 60 Pro 昆仑玻璃 卫星通话 旗舰手机 雅丹黑",
        "华为 Pura 70 Ultra 伸缩摄像头 1英寸大底 拍照神器",
        "华为 nova 12 活力版 前置6000万 轻薄自拍手机 12号色",
        "Huawei Mate X5 折叠屏 玄武钢化 鸿蒙生态 送无线充",
        # 小米系列
        "Xiaomi 14 Ultra 徕卡全焦段四摄 第三代骁龙8 大师人像",
        "红米 K70 至尊版 天玑9300+ 狂暴引擎 120W快充 学生游戏手机",
        "小米 Civi 4 Pro 前后双主摄 徕卡专业人像 轻薄潮流手机",
        # OPPO/vivo
        "OPPO Find X7 哈苏人像 超光影三摄 天玑9300 5G手机 正品保障",
        "vivo X100 Pro 蔡司APO超级长焦 蓝晶×天玑9300 自研影像芯片",
        "一加 Ace 3 Pro 第三代骁龙8 6100mAh大电池 极速闪充 性能猛兽",
        # 三星
        "Samsung Galaxy S24 Ultra 钛金属 2亿像素 AI智能手机 限定色",
        "三星 Galaxy Z Flip5 掌心折叠 小巧时尚 女生挚爱 吴京同款",
        # 荣耀
        "荣耀 Magic6 Pro 青海湖电池 鹰眼相机 5G旗舰 商务办公",
        # 其他及奇葩标题
        "【限时抢购】超薄大屏智能手机 学生价 老人机 备用机 包邮",
        "5G全网通手机 安卓智能 高清拍照 超长待机 大字大声 老年模式",
        "全新正品 百元机 学生党 游戏电竞手机 8核 6G+128G 不用卡顿",
        "拍照手机 美颜自拍 前后双摄 全面屏 水滴屏 不发热 长续航",
        "送妈妈 奶奶 老婆 情人节礼物 智能手机 简易模式 远程协助",
        "Huawei 畅享 70 6000mAh巨鲸电池 鸿蒙4系统 长辈手机 耐摔",
        "vivo Y100t 天玑8200 120W闪充 千元机 五年不卡 游戏体验",
        "三星 W24 心系天下 超高端商务折叠屏 陶瓷机身 尊享服务",
        "Nothing Phone 2a 透明机身 LED灯带 极简设计 小众手机",
        "realme 真我 GT5 Pro 骁龙8Gen3 240W闪充 性价比之王",
        "魅族 21 Note 骁龙8Gen2 窄边直屏 白色前面板 情怀回归",
        "索尼 Xperia 1 VI 4K OLED 电影感拍摄 3.5mm耳机孔 信仰充值",
        "努比亚 红魔9 Pro 游戏手机 内置风扇 960Hz触控肩键 RGB灯效",
        "【顺丰当天发】全新未激活 iPhone 15 Pro 原色钛金属 1TB 美版",
        "华为 Mate 60 RS 非凡大师 瑞红陶瓷 保值收藏 稀缺现货",
    ]
    return mock_data