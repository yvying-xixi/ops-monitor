"""自动化任务相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

TASK_TYPES = ("SERVICE_CHECK", "SERVICE_ACTION", "SERVICE_LOG")
ACTIONS = ("STATUS", "START", "STOP", "RESTART", "LOGS")
# 操作所需权限动作与是否需要二次确认
CONFIRM_REQUIRED_ACTIONS = ("START", "STOP", "RESTART")


class TaskCreate(BaseModel):
    """创建任务请求体。"""

    task_name: str = Field(..., min_length=1, max_length=128, description="任务名称")
    task_type: str = Field(..., description="SERVICE_CHECK/SERVICE_ACTION/SERVICE_LOG")
    action: str | None = Field(None, description="STATUS/START/STOP/RESTART/LOGS")
    service_name: str | None = Field(None, max_length=64, description="目标服务（白名单校验）")
    server_ids: list[int] = Field(..., min_length=1, description="目标服务器 ID 列表")
    schedule_type: str = Field("ONCE", description="ONCE/CRON")
    cron_expression: str | None = Field(None, max_length=128, description="Cron 表达式")
    timeout_seconds: int = Field(60, ge=10, le=3600, description="执行超时（秒）")
    confirmation_required: bool | None = Field(None, description="是否需二次确认，默认高风险操作需要")


class TaskOut(BaseModel):
    """任务响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_name: str
    task_type: str
    action: str | None
    service_name: str | None
    schedule_type: str
    cron_expression: str | None
    status: str
    timeout_seconds: int
    confirmation_required: int
    confirmed: bool
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_task(cls, task) -> "TaskOut":
        return cls(
            id=task.id,
            task_name=task.task_name,
            task_type=task.task_type,
            action=task.action,
            service_name=task.service_name,
            schedule_type=task.schedule_type,
            cron_expression=task.cron_expression,
            status=task.status,
            timeout_seconds=task.timeout_seconds,
            confirmation_required=task.confirmation_required,
            confirmed=task.confirmed_by is not None,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )


class TaskExecutionOut(BaseModel):
    """任务执行记录响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    server_id: int
    server_hostname: str | None = None
    status: str
    exit_code: int | None
    result_text: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None


class TaskLogOut(BaseModel):
    """任务执行日志响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    log_level: str
    log_content: str
    created_at: datetime
