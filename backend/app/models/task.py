from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, MEDIUMTEXT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.server import OpsServer
    from app.models.user import SysUser


class OpsTask(Base):
    __tablename__ = "ops_task"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uk_ops_task_idempotency"),
        Index("fk_ops_task_confirmed_by", "confirmed_by"),
        Index("idx_ops_task_creator_time", "created_by", "created_at"),
        Index("idx_ops_task_schedule", "schedule_type", "status"),
        Index("idx_ops_task_status", "status"),
        {"comment": "运维任务表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务ID")
    task_name: Mapped[str] = mapped_column(String(128), comment="任务名称")
    task_type: Mapped[str] = mapped_column(String(32), comment="SERVICE_CHECK/SERVICE_ACTION/SHELL_LIMITED")
    action: Mapped[str | None] = mapped_column(String(32), comment="STATUS/START/STOP/RESTART")
    service_name: Mapped[str | None] = mapped_column(String(64), comment="经过白名单校验的服务名称")
    schedule_type: Mapped[str] = mapped_column(
        String(16), default="ONCE", server_default=text("'ONCE'"), comment="ONCE/CRON"
    )
    cron_expression: Mapped[str | None] = mapped_column(String(128), comment="Cron表达式")
    status: Mapped[str] = mapped_column(
        String(24),
        default="CREATED",
        server_default=text("'CREATED'"),
        comment="CREATED/PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED",
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_ops_task_created_by"),
        comment="创建人",
    )
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="结束时间")
    timeout_seconds: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), default=300, server_default=text("300"), comment="超时时间，单位：秒"
    )
    max_attempts: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), default=3, server_default=text("3"), comment="最大尝试次数"
    )
    attempt: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), default=0, server_default=text("0"), comment="当前/最近尝试编号"
    )
    deadline_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="任务整体截止时间")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), comment="幂等键，防止重复创建")
    confirmation_required: Mapped[int] = mapped_column(
        TINYINT, default=0, server_default=text("0"), comment="是否需要二次确认"
    )
    confirmed_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_ops_task_confirmed_by"),
        comment="确认人",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="确认时间")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )

    targets: Mapped[list[OpsTaskTarget]] = relationship("OpsTaskTarget", back_populates="task")
    creator: Mapped[SysUser] = relationship("SysUser", foreign_keys=[created_by])
    confirmer: Mapped[SysUser | None] = relationship("SysUser", foreign_keys=[confirmed_by])


class OpsTaskTarget(Base):
    __tablename__ = "ops_task_target"
    __table_args__ = (
        UniqueConstraint("task_id", "server_id", name="uk_ops_task_target"),
        Index("idx_ops_task_target_server_id", "server_id"),
        Index("idx_ops_task_target_status", "target_status"),
        {"comment": "任务目标服务器表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务目标ID")
    task_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_task.id", name="fk_ops_task_target_task"),
        comment="任务ID",
    )
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_server.id", name="fk_ops_task_target_server"),
        comment="目标服务器ID",
    )
    target_status: Mapped[str] = mapped_column(
        String(24),
        default="PENDING",
        server_default=text("'PENDING'"),
        comment="PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )

    task: Mapped[OpsTask] = relationship("OpsTask", back_populates="targets")
    server: Mapped[OpsServer] = relationship("OpsServer")
    executions: Mapped[list[OpsTaskExecution]] = relationship("OpsTaskExecution", back_populates="target")


class OpsTaskExecution(Base):
    __tablename__ = "ops_task_execution"
    __table_args__ = (
        UniqueConstraint("task_id", "target_id", "attempt", name="uk_ops_task_execution_target"),
        Index("fk_ops_task_execution_target", "target_id"),
        Index("idx_ops_task_execution_server_time", "server_id", "created_at"),
        Index("idx_ops_task_execution_task_status", "task_id", "status"),
        Index("idx_ops_task_execution_retry", "status", "next_retry_at"),
        {"comment": "任务执行记录表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务执行记录ID")
    task_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_task.id", name="fk_ops_task_execution_task"),
        comment="任务ID",
    )
    target_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_task_target.id", name="fk_ops_task_execution_target"),
        comment="任务目标ID",
    )
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_server.id", name="fk_ops_task_execution_server"),
        comment="服务器ID",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        default="PENDING",
        server_default=text("'PENDING'"),
        comment="PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED/RETRYING/DEAD",
    )
    attempt: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), default=1, server_default=text("1"), comment="尝试编号"
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="下次重试时间")
    error_type: Mapped[str | None] = mapped_column(String(32), comment="标准化错误类型")
    exit_code: Mapped[int | None] = mapped_column(INTEGER, comment="进程退出码")
    result_text: Mapped[str | None] = mapped_column(MEDIUMTEXT, comment="执行结果")
    error_message: Mapped[str | None] = mapped_column(Text, comment="错误信息")
    started_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="结束时间")
    duration_ms: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="执行耗时，单位：毫秒")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )

    task: Mapped[OpsTask] = relationship("OpsTask")
    target: Mapped[OpsTaskTarget] = relationship("OpsTaskTarget", back_populates="executions")
    server: Mapped[OpsServer] = relationship("OpsServer")
    logs: Mapped[list[OpsTaskLog]] = relationship("OpsTaskLog", back_populates="execution")


class OpsTaskLog(Base):
    __tablename__ = "ops_task_log"
    __table_args__ = (
        Index("idx_ops_task_log_execution_time", "execution_id", "created_at"),
        {"comment": "任务执行日志表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务日志ID")
    execution_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_task_execution.id", name="fk_ops_task_log_execution"),
        comment="任务执行记录ID",
    )
    log_level: Mapped[str] = mapped_column(
        String(16), default="INFO", server_default=text("'INFO'"), comment="DEBUG/INFO/WARN/ERROR"
    )
    log_content: Mapped[str] = mapped_column(MEDIUMTEXT, comment="日志内容")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )

    execution: Mapped[OpsTaskExecution] = relationship("OpsTaskExecution", back_populates="logs")
