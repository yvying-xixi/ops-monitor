"""分布式调度协调：基于 Redis 的作业锁。

确保多 worker（同一容器 uvicorn --workers N）与多实例部署下，同一作业每轮
只被一个进程执行；执行完成后立即释放，避免影响下一周期。

锁不可用时（Redis 异常）默认跳过本轮，避免惊群。详见 ADR-011。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None

# 比较并删除：仅当锁值仍属于本进程 token 时才释放
_RELEASE_SCRIPT = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
)


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=3, decode_responses=True
        )
    return _client


def _release(key: str, token: str) -> None:
    try:
        _get_client().eval(_RELEASE_SCRIPT, 1, key, token)
    except redis.RedisError:
        # 释放失败时由 TTL 兜底
        logger.warning("调度锁释放失败（将由 TTL 兜底）: %s", key)


@contextmanager
def scheduler_lock(job_name: str, ttl_seconds: int) -> Iterator[bool]:
    """尝试获取作业锁。

    Yields:
        True 表示本进程获得锁，可执行作业；False 表示跳过本轮。
    """
    if not settings.SCHEDULER_LOCK_ENABLED:
        yield True
        return

    key = f"sched:lock:{job_name}"
    token = uuid.uuid4().hex
    try:
        acquired = bool(
            _get_client().set(key, token, nx=True, px=max(1, ttl_seconds) * 1000)
        )
    except redis.RedisError:
        logger.warning("调度锁不可用（Redis 异常），跳过本轮: %s", job_name)
        yield False
        return

    if not acquired:
        yield False
        return

    try:
        yield True
    finally:
        _release(key, token)


def run_with_lock(job_name: str, fn: Callable[[], None], ttl_seconds: int = 600) -> None:
    """在作业锁保护下执行 fn；未获锁则跳过。"""
    with scheduler_lock(job_name, ttl_seconds) as acquired:
        if acquired:
            fn()
