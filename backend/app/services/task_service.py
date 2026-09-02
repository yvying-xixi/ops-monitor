"""自动化任务服务：任务编排、分发与状态聚合。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    return datetime.now(timezone.utc).replace(tzinfo=None)


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

    def create_task(self, data: TaskCreate, *, creator_id: int) -> OpsTask:
        """创建任务：校验服务白名单与操作类型，创建 targets 与 executions。"""
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
        if task.status in ("SUCCESS", "FAILED", "CANCELLED", "TIMEOUT"):
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
        logs: str | None = None,
    ) -> OpsTaskExecution:
        """Agent 回传执行结果，更新执行与任务状态，记录日志。"""
        execution = self.execution_repo.get(execution_id)
        if execution is None or execution.server_id != server.id:
            raise AppException(ErrorCode.TASK_EXECUTION_NOT_FOUND, "执行记录不存在", http_status=404)
        if execution.status not in ("PENDING", "RUNNING"):
            raise AppException(ErrorCode.BAD_REQUEST, "执行已结束，不可重复回传", http_status=400)

        if status == "SUCCESS":
            self.execution_repo.finish(
                execution, status="SUCCESS", exit_code=exit_code, result_text=result_text
            )
            if logs:
                self.log_repo.record(execution.id, logs, "INFO")
        else:
            self.execution_repo.finish(
                execution, status="FAILED", exit_code=exit_code, error_message=error_message
            )
            if error_message:
                self.log_repo.record(execution.id, error_message, "ERROR")

        task = self.get_task_entity(execution.task_id)
        self._aggregate_task_status(task)
        self.db.commit()
        return execution

    # ---------- 调度扫描 ----------

    def scan_timeouts(self) -> int:
        """将超过任务超时时间的 RUNNING 执行置为 TIMEOUT。"""
        tasks = {t.id: t for t in self.task_repo.list_all(status="RUNNING")}
        total = 0
        for task in tasks.values():
            updated = self.execution_repo.mark_expired(task.timeout_seconds)
            if updated:
                self._aggregate_task_status(task)
                total += updated
        self.db.commit()
        return total

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
        executions = self.execution_repo.list_by_task(task.id)
        statuses = {e.status for e in executions}
        if any(s in ("PENDING", "RUNNING") for s in statuses):
            task.status = "RUNNING"
        elif any(s in ("FAILED", "TIMEOUT") for s in statuses):
            task.status = "FAILED"
        elif statuses and all(s == "SUCCESS" for s in statuses):
            task.status = "SUCCESS"
        elif statuses and all(s == "CANCELLED" for s in statuses):
            task.status = "CANCELLED"
        else:
            task.status = "SUCCESS" if "SUCCESS" in statuses else "FAILED"
        if task.status in ("SUCCESS", "FAILED", "TIMEOUT", "CANCELLED"):
            task.finished_at = _utcnow()
        self.db.flush()
