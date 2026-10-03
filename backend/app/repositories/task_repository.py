"""自动化任务仓储：任务、目标、执行记录与日志。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, func, select

from app.models import OpsTask, OpsTaskExecution, OpsTaskLog, OpsTaskTarget
from app.repositories.base import BaseRepository


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TaskRepository(BaseRepository[OpsTask]):
    """任务仓储。"""

    model = OpsTask

    def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        status: str | None = None,
        task_type: str | None = None,
    ) -> tuple[int, list[OpsTask]]:
        filters: dict = {}
        if status:
            filters["status"] = status
        if task_type:
            filters["task_type"] = task_type
        return self.list(page=page, page_size=page_size, order_by="-id", **filters)

    def list_pending_cron(self) -> list[OpsTask]:
        """查询已确认等待定时触发的 CRON 任务。"""
        stmt = select(OpsTask).where(
            OpsTask.schedule_type == "CRON",
            OpsTask.status.in_(["PENDING", "CREATED"]),
        )
        return list(self.db.scalars(stmt).all())

    def get_by_idempotency_key(self, key: str) -> OpsTask | None:
        """按幂等键查询任务。"""
        if not key:
            return None
        return self.get_by(idempotency_key=key)

    def delete_finished_tasks_before(self, cutoff: datetime) -> int:
        """删除过期的终态单次任务及其目标，返回删除的任务数。

        仅清理 `ONCE` 且已结束、且已无执行记录的任务；保留 `CRON` 调度定义。
        """
        task_ids = list(
            self.db.scalars(
                select(OpsTask.id).where(
                    OpsTask.schedule_type == "ONCE",
                    OpsTask.status.in_(("SUCCESS", "FAILED", "TIMEOUT", "CANCELLED", "DEAD")),
                    OpsTask.finished_at.isnot(None),
                    OpsTask.finished_at < cutoff,
                    ~exists().where(OpsTaskExecution.task_id == OpsTask.id),
                )
            ).all()
        )
        if not task_ids:
            return 0
        self.db.execute(delete(OpsTaskTarget).where(OpsTaskTarget.task_id.in_(task_ids)))
        result = self.db.execute(delete(OpsTask).where(OpsTask.id.in_(task_ids)))
        return result.rowcount or 0

    def count_by_status(self) -> dict:
        """按状态统计任务数量（指标用）。"""
        statuses = (
            "CREATED",
            "PENDING",
            "RUNNING",
            "SUCCESS",
            "FAILED",
            "TIMEOUT",
            "CANCELLED",
            "RETRYING",
            "DEAD",
        )
        stmt = select(OpsTask.status, func.count()).group_by(OpsTask.status)
        counts = {status: 0 for status in statuses}
        for status, count in self.db.execute(stmt):
            counts[status] = count
        return counts


class TaskTargetRepository(BaseRepository[OpsTaskTarget]):
    """任务目标仓储。"""

    model = OpsTaskTarget

    def create_targets(self, task_id: int, server_ids: list[int]) -> list[OpsTaskTarget]:
        targets = [OpsTaskTarget(task_id=task_id, server_id=sid) for sid in set(server_ids)]
        self.create_many(targets)
        return targets

    def list_by_task(self, task_id: int) -> list[OpsTaskTarget]:
        return self.list_all(task_id=task_id)


class TaskExecutionRepository(BaseRepository[OpsTaskExecution]):
    """任务执行记录仓储。"""

    model = OpsTaskExecution

    def create_executions(
        self, task_id: int, targets: list[OpsTaskTarget]
    ) -> list[OpsTaskExecution]:
        executions = [
            OpsTaskExecution(task_id=task_id, target_id=t.id, server_id=t.server_id, attempt=1)
            for t in targets
        ]
        self.create_many(executions)
        return executions

    def create_execution(
        self, *, task_id: int, target_id: int, server_id: int, attempt: int
    ) -> OpsTaskExecution:
        """为一次新的尝试创建执行记录。"""
        execution = OpsTaskExecution(
            task_id=task_id,
            target_id=target_id,
            server_id=server_id,
            attempt=attempt,
        )
        self.create(execution)
        return execution

    def list_due_retries(self, now: datetime, limit: int = 50) -> list[OpsTaskExecution]:
        """查询到达重试时间、状态为 RETRYING 的执行。"""
        stmt = (
            select(OpsTaskExecution)
            .where(
                OpsTaskExecution.status == "RETRYING",
                OpsTaskExecution.next_retry_at.isnot(None),
                OpsTaskExecution.next_retry_at <= now,
            )
            .order_by(OpsTaskExecution.next_retry_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def fetch_pending_by_server(self, server_id: int, limit: int = 10) -> list[OpsTaskExecution]:
        """领取服务器待执行的批次（限定任务已确认且未开始）。"""
        stmt = (
            select(OpsTaskExecution)
            .join(OpsTask, OpsTask.id == OpsTaskExecution.task_id)
            .where(
                OpsTaskExecution.server_id == server_id,
                OpsTaskExecution.status == "PENDING",
                OpsTask.status.in_(["PENDING", "RUNNING"]),
            )
            .order_by(OpsTaskExecution.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def mark_running(self, execution: OpsTaskExecution) -> OpsTaskExecution:
        execution.status = "RUNNING"
        execution.started_at = _utcnow()
        self.db.flush()
        return execution

    def finish(
        self,
        execution: OpsTaskExecution,
        *,
        status: str,
        exit_code: int | None = None,
        result_text: str | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> OpsTaskExecution:
        execution.status = status
        execution.exit_code = exit_code
        execution.result_text = result_text
        execution.error_message = error_message
        if error_type is not None:
            execution.error_type = error_type
        execution.finished_at = _utcnow()
        if execution.started_at is not None:
            execution.duration_ms = int(
                (execution.finished_at - execution.started_at).total_seconds() * 1000
            )
        self.db.flush()
        return execution

    def mark_retrying(
        self,
        execution: OpsTaskExecution,
        *,
        error_type: str,
        error_message: str | None,
        next_retry_at: datetime,
    ) -> OpsTaskExecution:
        """将失败的执行标记为等待重试。"""
        execution.status = "RETRYING"
        execution.error_type = error_type
        execution.error_message = error_message
        execution.next_retry_at = next_retry_at
        execution.finished_at = _utcnow()
        if execution.started_at is not None:
            execution.duration_ms = int(
                (execution.finished_at - execution.started_at).total_seconds() * 1000
            )
        self.db.flush()
        return execution

    def mark_dead(self, execution: OpsTaskExecution, *, error_type: str, error_message: str | None) -> OpsTaskExecution:
        """将重试耗尽 / 不可再重试的执行标记为 DEAD。"""
        execution.status = "DEAD"
        execution.error_type = error_type
        execution.error_message = error_message
        execution.next_retry_at = None
        execution.finished_at = _utcnow()
        if execution.started_at is not None:
            execution.duration_ms = int(
                (execution.finished_at - execution.started_at).total_seconds() * 1000
            )
        self.db.flush()
        return execution

    def list_by_task(self, task_id: int) -> list[OpsTaskExecution]:
        return self.list_all(task_id=task_id)

    def delete_terminal_before(self, cutoff: datetime) -> int:
        """删除过期终态执行记录及其日志，返回删除的执行数。

        仅清理已结束的执行（SUCCESS/FAILED/TIMEOUT/CANCELLED/DEAD），
        不影响进行中任务的状态聚合。
        """
        ids = list(
            self.db.scalars(
                select(OpsTaskExecution.id).where(
                    OpsTaskExecution.status.in_(("SUCCESS", "FAILED", "TIMEOUT", "CANCELLED", "DEAD")),
                    OpsTaskExecution.finished_at.isnot(None),
                    OpsTaskExecution.finished_at < cutoff,
                )
            ).all()
        )
        if not ids:
            return 0
        self.db.execute(delete(OpsTaskLog).where(OpsTaskLog.execution_id.in_(ids)))
        result = self.db.execute(delete(OpsTaskExecution).where(OpsTaskExecution.id.in_(ids)))
        return result.rowcount or 0

    def is_expired(self, execution: OpsTaskExecution, timeout_seconds: int) -> bool:
        """判断 RUNNING 执行是否已超过对应任务的超时时间。"""
        if execution.status != "RUNNING" or execution.started_at is None:
            return False
        return execution.started_at < _utcnow() - timedelta(seconds=timeout_seconds)

    def mark_timeout(self, execution: OpsTaskExecution, timeout_seconds: int) -> OpsTaskExecution:
        """将单个超时执行置为 TIMEOUT。"""
        execution.status = "TIMEOUT"
        execution.finished_at = _utcnow()
        execution.error_message = f"执行超时（{timeout_seconds}s）"
        self.db.flush()
        return execution


class TaskLogRepository(BaseRepository[OpsTaskLog]):
    """任务执行日志仓储。"""

    model = OpsTaskLog

    def record(self, execution_id: int, content: str, level: str = "INFO") -> OpsTaskLog:
        return self.create(
            OpsTaskLog(execution_id=execution_id, log_level=level, log_content=content)
        )

    def list_by_execution(self, execution_id: int) -> list[OpsTaskLog]:
        stmt = (
            select(OpsTaskLog)
            .where(OpsTaskLog.execution_id == execution_id)
            .order_by(OpsTaskLog.id.asc())
        )
        return list(self.db.scalars(stmt).all())
