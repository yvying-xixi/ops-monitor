"""后台定时任务：周期性刷新服务器 Agent 状态。"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories import ServerRepository

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
    _scheduler.start()
    logger.info("后台调度器已启动（Agent 状态刷新周期 %ss）", settings.AGENT_STATUS_REFRESH_SECONDS)


def shutdown_scheduler() -> None:
    """停止后台调度器。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("后台调度器已停止")
