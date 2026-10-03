"""Agent 任务 Worker：轮询领取并执行受控服务任务。"""

from __future__ import annotations

import logging

from agent import errors
from agent.errors import classify_failure, classify_validation_error
from agent.executor.service import ServiceExecutor
from agent.reporter.client import AgentClient, ReporterError
from agent.reporter.report import report_task_result

logger = logging.getLogger("agent.worker")

PENDING_PATH = "/api/v1/agent/tasks/pending"


class TaskWorker:
    """任务执行循环。

    每 `poll_interval` 秒轮询服务端待执行任务，逐个执行并回传结果。
    """

    def __init__(
        self,
        client: AgentClient,
        *,
        server_id: int,
        allowed_services: list[str],
        poll_interval: int = 5,
        stop,
    ) -> None:
        self.client = client
        self.server_id = server_id
        self.executor = ServiceExecutor(allowed_services)
        self.poll_interval = poll_interval
        self._stop = stop

    def run(self) -> None:
        """常驻执行循环（在线程中调用）。"""
        while not self._stop.is_set():
            try:
                self.poll_once()
            except ReporterError as exc:
                logger.warning("任务轮询失败: %s", exc)
            except Exception as exc:
                logger.exception("任务处理异常: %s", exc)
            self._stop.wait(self.poll_interval)

    def poll_once(self) -> int:
        """执行一轮拉取与处理，返回处理的任务数。"""
        pending = self.client.get(PENDING_PATH) or []
        processed = 0
        for task in pending:
            try:
                self._execute_one(task)
                processed += 1
            except Exception as exc:
                logger.exception("执行任务 %s 异常: %s", task.get("execution_id"), exc)
        return processed

    def _execute_one(self, task: dict) -> None:
        execution_id = task["execution_id"]
        action = task.get("action")
        service_name = task.get("service_name")
        timeout = task.get("timeout_seconds", 60)

        try:
            if action == "LOGS":
                success, output = self.executor.fetch_logs(service_name)
            else:
                success, output = self.executor.run_action(service_name, action, timeout=timeout)
        except ValueError as exc:
            logger.warning("任务 %s 被安全校验拦截: %s", execution_id, exc)
            report_task_result(
                self.client,
                execution_id=execution_id,
                status="FAILED",
                error_message=str(exc),
                error_type=classify_validation_error(str(exc)),
            )
            return
        except Exception as exc:
            logger.exception("任务 %s 执行异常: %s", execution_id, exc)
            report_task_result(
                self.client,
                execution_id=execution_id,
                status="FAILED",
                error_message=str(exc),
                error_type=errors.UNKNOWN,
            )
            return

        if success:
            report_task_result(
                self.client,
                execution_id=execution_id,
                status="SUCCESS",
                result_text=output,
                logs=output if action == "LOGS" else None,
            )
            return

        report_task_result(
            self.client,
            execution_id=execution_id,
            status="FAILED",
            error_message=output,
            error_type=classify_failure(output),
        )
