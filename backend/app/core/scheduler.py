"""后台定时任务：周期性刷新服务器 Agent 状态。"""

from __future__ import annotations

import functools
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.scheduler_lock import run_with_lock
from app.repositories import MetricRepository, ServerRepository
from app.services.alert_engine import AlertEngine
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _locked(job_name: str):
    """为作业加分布式锁，确保多 worker / 多实例下每轮只执行一次。"""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            run_with_lock(job_name, lambda: fn(*args, **kwargs), settings.SCHEDULER_LOCK_TTL_SECONDS)

        return wrapper

    return decorator


@_locked("cleanup_old_task_executions")
def _cleanup_old_task_executions() -> None:
    """删除超过保留期的终态执行记录、日志与已结束的单次任务。"""
    if not settings.TASK_CLEANUP_ENABLED:
        return
    db = SessionLocal()
    try:
        result = TaskService(db).cleanup_history(settings.TASK_RETENTION_DAYS)
        if result["executions"] or result["tasks"]:
            logger.info(
                "清理过期任务历史：执行 %s 条，任务 %s 条（保留 %s 天）",
                result["executions"],
                result["tasks"],
                settings.TASK_RETENTION_DAYS,
            )
    except Exception:
        logger.exception("任务历史清理失败")
    finally:
        db.close()


@_locked("scan_task_timeouts")
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


@_locked("dispatch_task_retries")
def _dispatch_task_retries() -> None:
    """将到期的 RETRYING 执行派发为下一次尝试。"""
    db = SessionLocal()
    try:
        created = TaskService(db).dispatch_retries()
        if created:
            logger.info("任务重试派发：新增 %s 个尝试", created)
    except Exception:
        logger.exception("任务重试派发失败")
    finally:
        db.close()


@_locked("fire_due_cron_tasks")
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


@_locked("evaluate_alerts")
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


@_locked("refresh_agent_status")
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


@_locked("cleanup_old_metrics")
def _cleanup_old_metrics() -> None:
    """将过期原始指标聚合归档到日表，并清理超期原始与聚合数据。"""
    if not settings.METRIC_CLEANUP_ENABLED:
        return
    db = SessionLocal()
    try:
        repo = MetricRepository(db)
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            days=settings.METRIC_RETENTION_DAYS
        )
        archived = repo.aggregate_daily(cutoff)
        deleted = repo.delete_older_than(settings.METRIC_RETENTION_DAYS)
        agg_deleted = repo.delete_daily_before(settings.METRIC_AGG_RETENTION_DAYS)
        db.commit()
        if archived or deleted or agg_deleted:
            logger.info(
                "指标归档/清理：日聚合 %s 行，删除原始 %s 条（保留 %s 天），删除聚合 %s 条（保留 %s 天）",
                archived,
                deleted,
                settings.METRIC_RETENTION_DAYS,
                agg_deleted,
                settings.METRIC_AGG_RETENTION_DAYS,
            )
    except Exception:
        logger.exception("指标归档/清理失败")
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
        _cleanup_old_task_executions,
        "interval",
        hours=24,
        id="cleanup_old_task_executions",
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
        _dispatch_task_retries,
        "interval",
        seconds=5,
        id="dispatch_task_retries",
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
