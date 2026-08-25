"""通用缓存管理组件——支持内存缓存和文件缓存两种后端。

使用方式：
    from .cache import CacheManager, cache_key

    # 内存缓存（默认 5 分钟 TTL）
    mem_cache = CacheManager(backend="memory", ttl=300)
    mem_cache.set("key", value)
    result = mem_cache.get("key")

    # 文件缓存（1 小时 TTL）
    file_cache = CacheManager(backend="file", ttl=3600, cache_dir="/path/to/cache")
    result = file_cache.get_or_compute("key", lambda: expensive_call())

    # 缓存键生成
    key = cache_key(arg1, arg2, option=value)
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable


class MemoryBackend:
    """内存缓存后端——dict + 时间戳。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, ttl: int) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


class FileBackend:
    """文件缓存后端——JSON 文件存储。"""

    def __init__(self, cache_dir: str | Path) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.json"

    def get(self, key: str, ttl: int) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("ts", 0) > ttl:
                path.unlink(missing_ok=True)
                return None
            return data.get("value")
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        path = self._path(key)
        try:
            path.write_text(
                json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def clear(self) -> None:
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)


class CacheManager:
    """通用缓存管理器，支持内存缓存和文件缓存。

    Args:
        backend: "memory" 或 "file"
        ttl: 缓存过期时间（秒），默认 300（5 分钟）
        cache_dir: 文件缓存目录（backend="file" 时必须）
    """

    def __init__(self, backend: str = "memory", ttl: int = 300, cache_dir: str | Path | None = None) -> None:
        self._ttl = ttl
        if backend == "memory":
            self._backend = MemoryBackend()
        elif backend == "file":
            if cache_dir is None:
                raise ValueError("backend='file' 时必须提供 cache_dir")
            self._backend = FileBackend(cache_dir)
        else:
            raise ValueError(f"不支持的 backend: {backend!r}，可选 'memory' 或 'file'")

    def get(self, key: str) -> Any | None:
        """获取缓存，过期返回 None。"""
        return self._backend.get(key, self._ttl)

    def set(self, key: str, value: Any) -> None:
        """设置缓存。"""
        self._backend.set(key, value)

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any]) -> Any:
        """获取缓存，不存在或已过期则调用 compute_fn 计算并缓存结果。

        Args:
            key: 缓存键
            compute_fn: 无参数的计算函数

        Returns:
            缓存值或计算结果
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        result = compute_fn()
        self.set(key, result)
        return result

    def clear(self) -> None:
        """清空缓存。"""
        self._backend.clear()


def cache_key(*args: Any, **kwargs: Any) -> str:
    """生成缓存键——对参数做 JSON 序列化后取 MD5。

    Args:
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        32 位十六进制 MD5 字符串
    """
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()
