import asyncio
from collections import defaultdict
from typing import List, Tuple, Optional

class StreamCache:
    """
    断点续传缓存管理器（单例模式，全局共享）。
    支持内存存储，可替换为 Redis 实现。
    """
    def __init__(self):
        # 缓存：thread_id -> list of (chunk_id, chunk_data)
        self._cache = defaultdict(list)
        # 计数器：thread_id -> 当前最大 chunk_id
        self._counter = defaultdict(int)
        # 异步锁，保证并发安全
        self._lock = asyncio.Lock()

    async def add_chunk(self, thread_id: str, chunk_id: int, data: str) -> None:
        """添加一个 chunk 到缓存（线程安全）"""
        async with self._lock:
            self._cache[thread_id].append((chunk_id, data))
            self._counter[thread_id] = chunk_id

    async def get_chunks(self, thread_id: str, start_id: int) -> List[Tuple[int, str]]:
        """
        获取指定 thread_id 中 chunk_id >= start_id 的所有 chunk。
        返回列表副本，避免迭代时被修改。
        """
        # 不加锁读取（因为 list 和 dict 在 Python 中并发读安全）
        cached = self._cache.get(thread_id, [])
        if not cached:
            return []
        # 由于数据量可能较大，使用列表推导并截取，返回新列表
        return [(cid, data) for cid, data in cached if cid >= start_id]

    def get_current_max_id(self, thread_id: str) -> int:
        """获取当前已生成的最大 chunk_id（非阻塞）"""
        return self._counter.get(thread_id, 0)

    async def clear_thread(self, thread_id: str) -> None:
        """清理指定会话的缓存（释放内存）"""
        async with self._lock:
            if thread_id in self._cache:
                del self._cache[thread_id]
            if thread_id in self._counter:
                del self._counter[thread_id]

# 全局单例实例
stream_cache = StreamCache()