"""分布式调度锁测试（依赖 Redis）。"""

from __future__ import annotations

from app.core.config import settings
from app.core.scheduler_lock import run_with_lock, scheduler_lock


def test_lock_is_exclusive_within_ttl():
    with scheduler_lock("test:exclusive", 30) as first:
        assert first is True
        with scheduler_lock("test:exclusive", 30) as second:
            assert second is False


def test_lock_released_after_run():
    # 释放后应可再次获取（同一周期结束后不影响下一轮）
    assert run_with_lock("test:release", lambda: None, ttl_seconds=30) is None
    with scheduler_lock("test:release", 30) as acquired:
        assert acquired is True


def test_run_with_lock_executes_when_acquired():
    calls: list[int] = []
    run_with_lock("test:execute", lambda: calls.append(1), ttl_seconds=30)
    assert calls == [1]


def test_lock_disabled_always_runs():
    original = settings.SCHEDULER_LOCK_ENABLED
    settings.SCHEDULER_LOCK_ENABLED = False
    try:
        with scheduler_lock("test:disabled", 30) as acquired:
            assert acquired is True
            with scheduler_lock("test:disabled", 30) as nested:
                assert nested is True
    finally:
        settings.SCHEDULER_LOCK_ENABLED = original
