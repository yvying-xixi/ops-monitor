"""Agent 请求防重放：基于 Redis 的 request_id 去重缓存。"""

from __future__ import annotations

import redis

from app.core.config import settings

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=3, decode_responses=True
        )
    return _client


def is_replayed(server_id: int, request_id: str, ttl_seconds: int) -> bool:
    """记录并判断 request_id 是否已出现。

    Args:
        server_id: 服务器 ID（隔离不同 Agent 的 key 空间）。
        request_id: 请求唯一标识。
        ttl_seconds: 缓存有效期（覆盖时钟窗口）。

    Returns:
        首次见到返回 False 并写入；重复返回 True。

    Raises:
        redis.RedisError: Redis 不可用。
    """
    key = f"agent:sig:{server_id}:{request_id}"
    created = _get_client().set(key, "1", nx=True, ex=ttl_seconds)
    return not bool(created)
