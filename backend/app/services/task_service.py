"""自动化任务服务：任务编排、分发与状态聚合。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.retry import UNKNOWN_ERROR_TYPE, backoff_seconds, classify_error, is_retryable
from app.exceptions import AppException, ErrorCode
from app.models import OpsServer, OpsTask, OpsTaskExecution
from app.repositories import ServerRepository
from app.repositories.server_repository import ServiceRepository
from app.repositories.task_repository import (
    TaskExecutionRepository,
    TaskLogRepository,
    TaskRepository,
    TaskTargetRepository,
)
from app.schemas.task import CONFIRM_REQUIRED_ACTIONS, TaskCreate

logger = logging.getLogger(__name__)

TASK_TYPE_ACTION = {
    "SERVICE_CHECK": "STATUS",
    "SERVICE_ACTION": None,  # START/STOP/RESTART
    "SERVICE_LOG": "LOGS",
}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TaskService:
    """任务业务逻辑，事务提交统一在此层完成。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.task_repo = TaskRepository(db)
        self.target_repo = TaskTargetRepository(db)
        self.execution_repo = TaskExecutionRepository(db)
        self.log_repo = TaskLogRepository(db)
        self.server_repo = ServerRepository(db)
        self.service_repo = ServiceRepository(db)

    # ---------- 创建 / 确认 / 列表 ----------

    def create_task(
        self, data: TaskCreate, *, creator_id: int, idempotency_key: str | None = None
    ) -> OpsTask:
        """创建任务：校验服务白名单与操作类型，创建 targets 与 executions。

        携带 `idempotency_key` 时，若已存在同键任务则直接返回该任务，避免网络重试造成重复创建。
        """
        if idempotency_key:
            existing = self.task_repo.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        action = self._normalize_action(data)
        servers = self._validate_servers(data.server_ids)
        self._validate_service_whitelist(servers, data.service_name, action)

        confirm_required = (
            data.confirmation_required
            if data.confirmation_required is not None
            else action in CONFIRM_REQUIRED_ACTIONS
        )
        status = "PENDING"
        if data.schedule_type == "CRON" or confirm_required:
            status = "CREATED"

        task = OpsTask(
            task_name=data.task_name,
            task_type=data.task_type,
            action=action,
            service_name=data.service_name,
            schedule_type=data.schedule_type,
            cron_expression=data.cron_expression,
            status=status,
            created_by=creator_id,
            timeout_seconds=data.timeout_seconds,
            max_attempts=data.max_attempts,
            attempt=0,
            deadline_at=_utcnow() + timedelta(seconds=data.timeout_seconds * data.max_attempts),
            idempotency_key=idempotency_key,
            confirmation_required=1 if confirm_required else 0,
        )
        self.task_repo.create(task)

        # targets 创建一次（ONCE 与 CRON 都保留目标集），executions 按需生成
        targets = self.target_repo.create_targets(task.id, [s.id for s in servers])
        if data.schedule_type == "ONCE":
            self.execution_repo.create_executions(task.id, targets)

        self.db.commit()
        return task

    def confirm_task(self, task_id: int, *, operator_id: int) -> OpsTask:
        """确认任务（高风险操作 / 定时任务需先确认）。"""
        task = self.get_task_entity(task_id)
        if task.status != "CREATED":
            raise AppException(ErrorCode.BAD_REQUEST, "任务当前无需确认", http_status=400)
        task.status = "PENDING"
        task.confirmed_by = operator_id
        task.confirmed_at = _utcnow()
        self.db.commit()
        return task

    def list_tasks(
        self, page: int, page_size: int, status: str | None, task_type: str | None
    ) -> tuple[int, list[OpsTask]]:
        return self.task_repo.list_tasks(page, page_size, status=status, task_type=task_type)

    def get_task_entity(self, task_id: int) -> OpsTask:
        task = self.task_repo.get(task_id)
        if task is None:
            raise AppException(ErrorCode.TASK_NOT_FOUND, "任务不存在", http_status=404)
        return task

    def get_task_detail(self, task_id: int) -> dict:
        """任务详情：包含各服务器执行结果。"""
        task = self.get_task_entity(task_id)
        executions = self.execution_repo.list_by_task(task_id)
        server_ids = {e.server_id for e in executions}
        hostnames = {}
        if server_ids:
            for sid, hostname in self.db.execute(
                select(OpsServer.id, OpsServer.hostname).where(OpsServer.id.in_(server_ids))
            ).all():
                hostnames[sid] = hostname

        execution_list = []
        for e in executions:
            logs = self.log_repo.list_by_execution(e.id)
            execution_list.append(
                {
                    "id": e.id,
                    "task_id": e.task_id,
                    "server_id": e.server_id,
                    "server_hostname": hostnames.get(e.server_id),
                    "status": e.status,
                    "exit_code": e.exit_code,
                    "result_text": e.result_text,
                    "error_message": e.error_message,
                    "started_at": e.started_at,
                    "finished_at": e.finished_at,
                    "duration_ms": e.duration_ms,
                    "logs": [log.log_content for log in logs],
                }
            )
        return {
            "task": task,
            "executions": execution_list,
        }

    def cancel_task(self, task_id: int) -> OpsTask:
        """取消任务：未完成的执行置 CANCELLED。"""
        task = self.get_task_entity(task_id)
        if task.status in ("SUCCESS", "FAILED", "CANCELLED", "TIMEOUT", "DEAD"):
            raise AppException(ErrorCode.BAD_REQUEST, "任务已结束，无法取消", http_status=400)
        for execution in self.execution_repo.list_by_task(task.id):
            if execution.status == "PENDING":
                self.execution_repo.finish(execution, status="CANCELLED", error_message="任务被取消")
        self._aggregate_task_status(task)
        self.db.commit()
        return task

    # ---------- Agent 分发与回传 ----------

    def fetch_pending(self, server: OpsServer) -> list[dict]:
        """Agent 轮询领取待执行任务，返回执行参数并标记 RUNNING。"""
        executions = self.execution_repo.fetch_pending_by_server(server.id)
        result = []
        for execution in executions:
            task = execution.task
            self.execution_repo.mark_running(execution)
            task.status = "RUNNING"
            task.started_at = task.started_at or _utcnow()
            result.append(
                {
                    "execution_id": execution.id,
                    "task_id": task.id,
                    "action": task.action,
                    "service_name": task.service_name,
                    "timeout_seconds": task.timeout_seconds,
                }
            )
        self.db.commit()
        return result

    def report_result(
        self,
        server: OpsServer,
        *,
        execution_id: int,
        status: str,
        exit_code: int | None = None,
        result_text: str | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
        logs: str | None = None,
    ) -> OpsTaskExecution:
        """Agent 回传执行结果，更新执行与任务状态，记录日志。

        - 已结束的执行重复回传时返回既有结果（幂等），不再报 400。
        - 失败时按错误分类决定是否进入 RETRYING，或终态 DEAD / FAILED。
        """
        execution = self.execution_repo.get(execution_id)
        if execution is None or execution.server_id != server.id:
            raise AppException(ErrorCode.TASK_EXECUTION_NOT_FOUND, "执行记录不存在", http_status=404)
        if execution.status in ("SUCCESS", "FAILED", "TIMEOUT", "CANCELLED", "DEAD"):
            return execution

        task = self.get_task_entity(execution.task_id)

        if status == "SUCCESS":
            self.execution_repo.finish(
                execution, status="SUCCESS", exit_code=exit_code, result_text=result_text
            )
            self.log_repo.record(execution.id, logs or result_text or "执行成功", "INFO")
        else:
            failed_type = classify_error(error_type, error_message)
            if is_retryable(error_type, error_message) and self._can_retry(task, execution):
                next_retry_at = _utcnow() + timedelta(seconds=backoff_seconds(execution.attempt))
                self.execution_repo.mark_retrying(
                    execution,
                    error_type=failed_type,
                    error_message=error_message,
                    next_retry_at=next_retry_at,
                )
                self.log_repo.record(
                    execution.id,
                    f"第 {execution.attempt} 次执行失败（{failed_type}），计划 {next_retry_at.isoformat()} 重试",
                    "ERROR",
                )
            elif is_retryable(error_type, error_message):
                self.execution_repo.mark_dead(
                    execution,
                    error_type=failed_type,
                    error_message=error_message or "重试预算耗尽",
                )
                self.log_repo.record(execution.id, f"执行失败且不可再重试（{failed_type}）", "ERROR")
            else:
                self.execution_repo.finish(
                    execution,
                    status="FAILED",
                    exit_code=exit_code,
                    error_message=error_message,
                    error_type=failed_type,
                )
                self.log_repo.record(execution.id, error_message or "执行失败", "ERROR")

        self._aggregate_task_status(task)
        self.db.commit()
        return execution

    # ---------- 调度扫描 ----------

    def scan_timeouts(self) -> int:
        """将超过**各自任务**超时时间的 RUNNING 执行置为 TIMEOUT。"""
        total = 0
        for task in self.task_repo.list_all(status="RUNNING"):
            expired = [
                execution
                for execution in self.execution_repo.list_by_task(task.id)
                if self.execution_repo.is_expired(execution, task.timeout_seconds)
            ]
            for execution in expired:
                self.execution_repo.mark_timeout(execution, task.timeout_seconds)
                total += 1
            if expired:
                self._aggregate_task_status(task)
        self.db.commit()
        return total

    def dispatch_retries(self, limit: int = 50) -> int:
        """将到期的 RETRYING 执行转为下一次 attempt（新执行记录）。

        Returns:
            本轮创建的新尝试数量。
        """
        now = _utcnow()
        due = self.execution_repo.list_due_retries(now, limit)
        created = 0
        for execution in due:
            task = self.get_task_entity(execution.task_id)
            # 任务已终止（取消/已完成）时，当前等待中的执行直接归档为 FAILED。
            if task.status in ("SUCCESS", "FAILED", "CANCELLED", "TIMEOUT", "DEAD"):
                self.execution_repo.finish(
                    execution,
                    status="FAILED",
                    error_message=execution.error_message,
                    error_type=execution.error_type,
                )
                continue

            if not self._can_retry(task, execution):
                self.execution_repo.mark_dead(
                    execution,
                    error_type=execution.error_type or UNKNOWN_ERROR_TYPE,
                    error_message=execution.error_message or "重试预算耗尽",
                )
                self.log_repo.record(execution.id, "重试预算耗尽，任务终止", "ERROR")
                self._aggregate_task_status(task)
                continue

            next_attempt = execution.attempt + 1
            # 归档当前失败的尝试
            self.execution_repo.finish(
                execution,
                status="FAILED",
                error_message=execution.error_message,
                error_type=execution.error_type,
            )
            self.execution_repo.create_execution(
                task_id=task.id,
                target_id=execution.target_id,
                server_id=execution.server_id,
                attempt=next_attempt,
            )
            task.attempt = next_attempt
            target = self.target_repo.get(execution.target_id)
            if target is not None:
                target.target_status = "PENDING"
            self.log_repo.record(execution.id, f"已创建第 {next_attempt} 次尝试", "INFO")
            self._aggregate_task_status(task)
            created += 1

        self.db.commit()
        return created

    def cleanup_executions(self, retention_days: int) -> int:
        """清理超过保留期的终态执行记录及其日志。"""
        cutoff = _utcnow() - timedelta(days=retention_days)
        deleted = self.execution_repo.delete_terminal_before(cutoff)
        self.db.commit()
        return deleted

    @staticmethod
    def _can_retry(task: OpsTask, execution: OpsTaskExecution) -> bool:
        """是否仍有重试预算：尝试次数与整体 deadline 均未耗尽。"""
        if execution.attempt >= task.max_attempts:
            return False
        if task.deadline_at is not None and _utcnow() >= task.deadline_at:
            return False
        return True

    def fire_due_cron(self) -> int:
        """触发到期的 CRON 任务（单次执行批次），返回触发数量。"""
        fired = 0
        now = _utcnow()
        for task in self.task_repo.list_pending_cron():
            if task.schedule_type != "CRON" or not task.cron_expression:
                continue
            base = task.created_at or now
            try:
                next_time = croniter(task.cron_expression, base).get_next(datetime)
            except Exception:
                logger.warning("任务 %s Cron 表达式非法: %s", task.id, task.cron_expression)
                continue
            if next_time <= now:
                # 已触发过的任务状态为 RUNNING，不会被本扫描再次选中；
                # 此处仅对尚无执行记录的到期任务生成执行批次。
                targets = self.target_repo.list_by_task(task.id)
                self.execution_repo.create_executions(task.id, targets)
                task.status = "RUNNING"
                task.started_at = task.started_at or now
                fired += 1
        self.db.commit()
        return fired

    # ---------- 辅助 ----------

    def _normalize_action(self, data: TaskCreate) -> str:
        allowed = TASK_TYPE_ACTION[data.task_type]
        if allowed is not None:
            if data.action not in (None, allowed):
                raise AppException(ErrorCode.TASK_ACTION_INVALID, f"{data.task_type} 仅支持 {allowed}", http_status=400)
            return allowed
        if data.action not in ("START", "STOP", "RESTART"):
            raise AppException(ErrorCode.TASK_ACTION_INVALID, "SERVICE_ACTION 需指定 START/STOP/RESTART", http_status=400)
        return data.action

    def _validate_servers(self, server_ids: list[int]) -> list[OpsServer]:
        servers = []
        for sid in set(server_ids):
            server = self.server_repo.get(sid)
            if server is None:
                raise AppException(ErrorCode.SERVER_NOT_FOUND, f"服务器不存在: {sid}", http_status=404)
            servers.append(server)
        return servers

    def _validate_service_whitelist(
        self, servers: list[OpsServer], service_name: str | None, action: str
    ) -> None:
        if action in ("STATUS", "LOGS"):
            return  # 只读操作不需白名单
        if not service_name:
            raise AppException(ErrorCode.BAD_REQUEST, "缺少目标服务", http_status=400)
        for server in servers:
            service = self.service_repo.get_by_server_service(server.id, service_name)
            if service is None or service.is_whitelisted != 1:
                raise AppException(
                    ErrorCode.SERVICE_NOT_WHITELISTED,
                    f"{server.hostname} 上的服务 {service_name} 不允许受控操作",
                    http_status=403,
                )

    def _aggregate_task_status(self, task: OpsTask) -> None:
        """按每个 target 的最新 attempt 汇总任务状态。

        重试会产生多条同 target 的执行记录，历史 FAILED 不得覆盖最新结果。
        """
        executions = self.execution_repo.list_by_task(task.id)
        if not executions:
            task.status = "PENDING"
            return

        latest: dict[int, OpsTaskExecution] = {}
        for execution in executions:
            current = latest.get(execution.target_id)
            if current is None or execution.attempt > current.attempt:
                latest[execution.target_id] = execution
        statuses = {e.status for e in latest.values()}

        if "RETRYING" in statuses:
            task.status = "RETRYING"
        elif any(s in ("PENDING", "RUNNING") for s in statuses):
            task.status = "RUNNING"
        elif "DEAD" in statuses:
            task.status = "DEAD"
        elif any(s in ("FAILED", "TIMEOUT") for s in statuses):
            task.status = "FAILED"
        elif all(s == "SUCCESS" for s in statuses):
            task.status = "SUCCESS"
        elif all(s == "CANCELLED" for s in statuses):
            task.status = "CANCELLED"
        else:
            task.status = "SUCCESS" if "SUCCESS" in statuses else "FAILED"

        if task.status in ("SUCCESS", "FAILED", "TIMEOUT", "CANCELLED", "DEAD"):
            task.finished_at = _utcnow()
        self.db.flush()
