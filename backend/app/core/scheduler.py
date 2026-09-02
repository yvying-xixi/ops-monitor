"""后台定时任务：周期性刷新服务器 Agent 状态。"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories import MetricRepository, ServerRepository
from app.services.alert_engine import AlertEngine
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _scan_task_timeouts() -> None:
    """将超时执行的任务置为 TIMEOUT。"""
    db = SessionLocal()
    try:
        updated = TaskService(db).scan_timeouts()
        if updated:
            logger.info("任务超时扫描：%s 个执行超时", updated)
    except Exception:
        logger.exception("任务超时扫描失败")
    finally:
        db.close()


def _fire_due_cron_tasks() -> None:
    """触发到期的 CRON 任务。"""
    db = SessionLocal()
    try:
        fired = TaskService(db).fire_due_cron()
        if fired:
            logger.info("定时任务触发：%s 个", fired)
    except Exception:
        logger.exception("定时任务触发失败")
    finally:
        db.close()


def _evaluate_alerts() -> None:
    """执行一轮告警规则评估。"""
    db = SessionLocal()
    try:
        created = AlertEngine(db).evaluate_all()
        if created:
            logger.info("告警引擎：新增 %s 条告警", created)
    except Exception:
        logger.exception("告警规则评估失败")
    finally:
        db.close()


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
    _scheduler.add_job(
        _evaluate_alerts,
        "interval",
        seconds=settings.ALERT_EVALUATE_INTERVAL_SECONDS,
        id="evaluate_alerts",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _scan_task_timeouts,
        "interval",
        seconds=30,
        id="scan_task_timeouts",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _fire_due_cron_tasks,
        "interval",
        seconds=30,
        id="fire_due_cron_tasks",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "后台调度器已启动（状态刷新 %ss，指标清理 24h，告警评估 %ss，任务超时/定时 30s）",
        settings.AGENT_STATUS_REFRESH_SECONDS,
        settings.ALERT_EVALUATE_INTERVAL_SECONDS,
    )


def shutdown_scheduler() -> None:
    """停止后台调度器。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("后台调度器已停止")
