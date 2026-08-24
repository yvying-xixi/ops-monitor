from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, FetchedValue, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AlertRule(Base):
    __tablename__ = "alert_rule"
    __table_args__ = {"comment": "告警规则表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="告警规则ID")
    rule_name: Mapped[str] = mapped_column(String(128), comment="规则名称")
    metric_type: Mapped[str] = mapped_column(String(64), comment="CPU/MEMORY/DISK/LOAD/AGENT/SERVICE/CONTAINER")
    target_type: Mapped[str] = mapped_column(String(32), default="SERVER", comment="SERVER/DISK/CONTAINER/SERVICE")
    severity: Mapped[str] = mapped_column(String(16), comment="WARNING/CRITICAL")
    operator: Mapped[str] = mapped_column(String(8), comment="GT/GTE/LT/LTE/EQ")
    threshold: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="数值阈值")
    duration_seconds: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, comment="持续异常时间，单位：秒")
    recovery_threshold: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="恢复阈值，可为空")
    enabled: Mapped[int] = mapped_column(SMALLINT, default=1, comment="是否启用")
    description: Mapped[str | None] = mapped_column(String(500), comment="规则描述")
    created_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("sys_user.id"), comment="创建人"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    events: Mapped[list[AlertEvent]] = relationship("AlertEvent", back_populates="rule")


class AlertEvent(Base):
    __tablename__ = "alert_event"
    __table_args__ = {"comment": "告警事件表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="告警事件ID")
    rule_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("alert_rule.id"), comment="告警规则ID"
    )
    server_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    resource_type: Mapped[str] = mapped_column(String(32), default="SERVER", comment="资源类型")
    resource_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="资源ID")
    alert_key: Mapped[str] = mapped_column(String(255), comment="告警指纹，用于活动告警去重")
    metric_type: Mapped[str] = mapped_column(String(64), comment="指标类型")
    severity: Mapped[str] = mapped_column(String(16), comment="WARNING/CRITICAL")
    status: Mapped[str] = mapped_column(String(24), default="PENDING", comment="PENDING/FIRING/ACKNOWLEDGED/RESOLVED")
    is_active: Mapped[int | None] = mapped_column(
        SMALLINT,
        server_default=FetchedValue(),
        comment="活动告警标记（生成列）",
    )
    first_fired_at: Mapped[datetime | None] = mapped_column(DateTime, comment="首次触发时间")
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最近触发时间")
    acknowledged_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("sys_user.id"), comment="确认人"
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, comment="确认时间")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, comment="恢复时间")
    current_value: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="当前指标值")
    threshold_value: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="触发阈值")
    message: Mapped[str] = mapped_column(String(500), comment="告警消息")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    rule: Mapped[AlertRule] = relationship("AlertRule", back_populates="events")
    server: Mapped[OpsServer | None] = relationship("OpsServer")
    acknowledged_by_user: Mapped[SysUser | None] = relationship("SysUser", foreign_keys=[acknowledged_by])
    logs: Mapped[list[AlertEventLog]] = relationship("AlertEventLog", back_populates="event")


class AlertEventLog(Base):
    __tablename__ = "alert_event_log"
    __table_args__ = {"comment": "告警状态变化日志表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="告警事件日志ID")
    event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("alert_event.id"), comment="告警事件ID"
    )
    old_status: Mapped[str | None] = mapped_column(String(24), comment="原状态")
    new_status: Mapped[str] = mapped_column(String(24), comment="新状态")
    current_value: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="事件值")
    message: Mapped[str | None] = mapped_column(String(500), comment="状态变化说明")
    operator_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("sys_user.id"), comment="操作人，系统操作可为空"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    event: Mapped[AlertEvent] = relationship("AlertEvent", back_populates="logs")
    operator: Mapped[SysUser | None] = relationship("SysUser")
