from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.server import OpsServer
    from app.models.user import SysUser


class SysLoginLog(Base):
    __tablename__ = "sys_login_log"
    __table_args__ = (
        Index("idx_sys_login_log_status_time", "login_status", "created_at"),
        Index("idx_sys_login_log_user_time", "user_id", "created_at"),
        Index("idx_sys_login_log_username_time", "username", "created_at"),
        {"comment": "用户登录日志表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="登录日志ID")
    user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_sys_login_log_user"),
        comment="用户ID，登录失败时可为空",
    )
    username: Mapped[str] = mapped_column(String(64), comment="登录用户名")
    login_ip: Mapped[str | None] = mapped_column(String(64), comment="登录IP")
    user_agent: Mapped[str | None] = mapped_column(String(500), comment="浏览器User-Agent")
    login_status: Mapped[str] = mapped_column(String(16), comment="SUCCESS/FAILED/LOCKED")
    failure_reason: Mapped[str | None] = mapped_column(String(255), comment="失败原因")
    request_id: Mapped[str | None] = mapped_column(String(64), comment="请求ID")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[SysUser | None] = relationship("SysUser")


class SysOperationLog(Base):
    __tablename__ = "sys_operation_log"
    __table_args__ = (
        Index("idx_sys_operation_log_created_at", "created_at"),
        Index("idx_sys_operation_log_module_time", "module", "created_at"),
        Index("idx_sys_operation_log_server_time", "server_id", "created_at"),
        Index("idx_sys_operation_log_status_time", "result_status", "created_at"),
        Index("idx_sys_operation_log_user_time", "user_id", "created_at"),
        {"comment": "系统操作审计日志表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="操作日志ID")
    user_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_sys_operation_log_user"),
        comment="操作用户ID",
    )
    username: Mapped[str | None] = mapped_column(String(64), comment="操作用户名快照")
    module: Mapped[str] = mapped_column(String(64), comment="操作模块")
    operation: Mapped[str] = mapped_column(String(64), comment="操作类型")
    http_method: Mapped[str | None] = mapped_column(String(16), comment="HTTP方法")
    request_path: Mapped[str | None] = mapped_column(String(255), comment="请求路径")
    target_type: Mapped[str | None] = mapped_column(String(32), comment="目标类型")
    target_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="目标ID")
    server_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_server.id", name="fk_sys_operation_log_server"),
        comment="目标服务器ID",
    )
    request_ip: Mapped[str | None] = mapped_column(String(64), comment="请求IP")
    request_id: Mapped[str | None] = mapped_column(String(64), comment="请求ID")
    request_params: Mapped[dict | None] = mapped_column(JSON, comment="请求参数，禁止记录密码和Token")
    result_status: Mapped[str] = mapped_column(String(24), comment="SUCCESS/FAILED")
    error_message: Mapped[str | None] = mapped_column(Text, comment="错误信息")
    duration_ms: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="请求耗时，单位：毫秒")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )

    user: Mapped[SysUser | None] = relationship("SysUser")
    server: Mapped[OpsServer | None] = relationship("OpsServer")
