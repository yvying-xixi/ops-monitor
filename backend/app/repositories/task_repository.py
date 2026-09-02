"""自动化任务仓储：任务、目标、执行记录与日志。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

from app.models import OpsTask, OpsTaskExecution, OpsTaskLog, OpsTaskTarget
from app.repositories.base import BaseRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
            OpsTaskExecution(task_id=task_id, target_id=t.id, server_id=t.server_id)
            for t in targets
        ]
        self.create_many(executions)
        return executions

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
    ) -> OpsTaskExecution:
        execution.status = status
        execution.exit_code = exit_code
        execution.result_text = result_text
        execution.error_message = error_message
        execution.finished_at = _utcnow()
        if execution.started_at is not None:
            execution.duration_ms = int(
                (execution.finished_at - execution.started_at).total_seconds() * 1000
            )
        self.db.flush()
        return execution

    def list_by_task(self, task_id: int) -> list[OpsTaskExecution]:
        return self.list_all(task_id=task_id)

    def mark_expired(self, timeout_seconds: int) -> int:
        """将超时未完成的 RUNNING 执行置为 TIMEOUT。"""
        cutoff = _utcnow() - timedelta(seconds=timeout_seconds)
        stmt = (
            update(OpsTaskExecution)
            .where(
                OpsTaskExecution.status == "RUNNING",
                OpsTaskExecution.started_at < cutoff,
            )
            .values(
                status="TIMEOUT",
                finished_at=_utcnow(),
                error_message=f"执行超时（{timeout_seconds}s）",
            )
        )
        return self.db.execute(stmt).rowcount or 0


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
