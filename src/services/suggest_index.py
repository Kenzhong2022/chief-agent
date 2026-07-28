from collections import defaultdict
import json
import os

INDEX_FILE = "prefix_index.json"

def build_prefix_index(word_score_map):
    # 你已有的实现
    index = defaultdict(list)
    for word, score in word_score_map.items():
        for i in range(1, len(word) + 1):
            prefix = word[:i]
            index[prefix].append({"word": word, "score": score})
    for prefix in index:
        index[prefix].sort(key=lambda x: x["score"], reverse=True)
    return dict(index)  # 转成普通 dict 方便序列化

def save_index(index, filepath=INDEX_FILE):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def load_index(filepath=INDEX_FILE):
    if not os.path.exists(filepath):
        print(f"⚠️ 索引文件 {filepath} 不存在，返回空索引")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)