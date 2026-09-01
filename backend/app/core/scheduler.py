"""后台定时任务：周期性刷新服务器 Agent 状态。"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories import MetricRepository, ServerRepository

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _refresh_agent_statuses() -> None:
    """按最后心跳时间刷新所有服务器的 Agent 状态。"""
    db = SessionLocal()
    try:
        updated = ServerRepository(db).refresh_agent_statuses()
        db.commit()
        if updated:
            logger.info("Agent 状态刷新完成，更新 %s 台服务器", updated)
    except Exception:
        logger.exception("Agent 状态刷新失败")
    finally:
        db.close()


def _cleanup_old_metrics() -> None:
    """删除超过保留期的历史指标。"""
    if not settings.METRIC_CLEANUP_ENABLED:
        return
    db = SessionLocal()
    try:
        deleted = MetricRepository(db).delete_older_than(settings.METRIC_RETENTION_DAYS)
        db.commit()
        if deleted:
            logger.info("清理过期指标 %s 条（保留 %s 天）", deleted, settings.METRIC_RETENTION_DAYS)
    except Exception:
        logger.exception("指标清理失败")
    finally:
        db.close()


def setup_scheduler() -> None:
    """启动后台调度器（仅随应用 lifespan 调用一次）。"""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _refresh_agent_statuses,
        "interval",
        seconds=settings.AGENT_STATUS_REFRESH_SECONDS,
        id="refresh_agent_status",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _cleanup_old_metrics,
        "interval",
        hours=24,
        id="cleanup_old_metrics",
        max_instances=1,
        coalesce=True,
        next_run_time=None,
    )
    _scheduler.start()
    logger.info(
        "后台调度器已启动（状态刷新 %ss，指标清理 24h）",
        settings.AGENT_STATUS_REFRESH_SECONDS,
    )


def shutdown_scheduler() -> None:
    """停止后台调度器。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("后台调度器已停止")
