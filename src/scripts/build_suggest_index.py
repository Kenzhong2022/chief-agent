import sys

sys.path.append(".")  # 确保能找到 src 模块

from src.agents.suggest_agent import build_agent
from src.services.suggest_index import build_prefix_index, save_index


def main():
    # 1. 构建 Agent（无检查点，无状态）
    agent = build_agent(checkpointer=None)

    # 2. 调用 Agent 清洗数据
    result = agent.invoke({
        "messages": [("user", "请清洗手机类目的商品标题，生成联想词")]
    })
    cleaned = result['structured_response']  # CleanedProducts 对象

    # 3. 转成 {词: 分} 字典
    word_score_map = {item.word: item.score for item in cleaned.suggestions}
    print(f"✅ 生成联想词 {len(word_score_map)} 条")

    # 4. 构建前缀索引并保存到文件
    prefix_index = build_prefix_index(word_score_map)
    save_index(prefix_index)
    print(f"✅ 前缀索引已保存，共 {len(prefix_index)} 个前缀")


if __name__ == "__main__":
    main()