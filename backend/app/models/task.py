from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, MEDIUMTEXT, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OpsTask(Base):
    __tablename__ = "ops_task"
    __table_args__ = {"comment": "运维任务表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务ID")
    task_name: Mapped[str] = mapped_column(String(128), comment="任务名称")
    task_type: Mapped[str] = mapped_column(String(32), comment="SERVICE_CHECK/SERVICE_ACTION/SHELL_LIMITED")
    action: Mapped[str | None] = mapped_column(String(32), comment="STATUS/START/STOP/RESTART")
    service_name: Mapped[str | None] = mapped_column(String(64), comment="经过白名单校验的服务名称")
    schedule_type: Mapped[str] = mapped_column(String(16), default="ONCE", comment="ONCE/CRON")
    cron_expression: Mapped[str | None] = mapped_column(String(128), comment="Cron表达式")
    status: Mapped[str] = mapped_column(
        String(24), default="CREATED", comment="CREATED/PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED"
    )
    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("sys_user.id"), comment="创建人"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, comment="结束时间")
    timeout_seconds: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=300, comment="超时时间，单位：秒")
    confirmation_required: Mapped[int] = mapped_column(SMALLINT, default=0, comment="是否需要二次确认")
    confirmed_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("sys_user.id"), comment="确认人"
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="确认时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    targets: Mapped[list[OpsTaskTarget]] = relationship("OpsTaskTarget", back_populates="task")
    creator: Mapped[SysUser] = relationship("SysUser", foreign_keys=[created_by])
    confirmer: Mapped[SysUser | None] = relationship("SysUser", foreign_keys=[confirmed_by])


class OpsTaskTarget(Base):
    __tablename__ = "ops_task_target"
    __table_args__ = {"comment": "任务目标服务器表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务目标ID")
    task_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_task.id"), comment="任务ID"
    )
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="目标服务器ID"
    )
    target_status: Mapped[str] = mapped_column(
        String(24), default="PENDING", comment="PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    task: Mapped[OpsTask] = relationship("OpsTask", back_populates="targets")
    server: Mapped[OpsServer] = relationship("OpsServer")
    executions: Mapped[list[OpsTaskExecution]] = relationship("OpsTaskExecution", back_populates="target")


class OpsTaskExecution(Base):
    __tablename__ = "ops_task_execution"
    __table_args__ = {"comment": "任务执行记录表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务执行记录ID")
    task_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_task.id"), comment="任务ID"
    )
    target_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_task_target.id"), comment="任务目标ID"
    )
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    status: Mapped[str] = mapped_column(
        String(24), default="PENDING", comment="PENDING/RUNNING/SUCCESS/FAILED/TIMEOUT/CANCELLED"
    )
    exit_code: Mapped[int | None] = mapped_column(INTEGER, comment="进程退出码")
    result_text: Mapped[str | None] = mapped_column(MEDIUMTEXT, comment="执行结果")
    error_message: Mapped[str | None] = mapped_column(Text, comment="错误信息")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, comment="结束时间")
    duration_ms: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="执行耗时，单位：毫秒")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    task: Mapped[OpsTask] = relationship("OpsTask")
    target: Mapped[OpsTaskTarget] = relationship("OpsTaskTarget", back_populates="executions")
    server: Mapped[OpsServer] = relationship("OpsServer")
    logs: Mapped[list[OpsTaskLog]] = relationship("OpsTaskLog", back_populates="execution")


class OpsTaskLog(Base):
    __tablename__ = "ops_task_log"
    __table_args__ = {"comment": "任务执行日志表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="任务日志ID")
    execution_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_task_execution.id"), comment="任务执行记录ID"
    )
    log_level: Mapped[str] = mapped_column(String(16), default="INFO", comment="DEBUG/INFO/WARN/ERROR")
    log_content: Mapped[str] = mapped_column(MEDIUMTEXT, comment="日志内容")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    execution: Mapped[OpsTaskExecution] = relationship("OpsTaskExecution", back_populates="logs")
