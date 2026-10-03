from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Computed, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.server import OpsServer
    from app.models.user import SysUser


class AlertRule(Base):
    __tablename__ = "alert_rule"
    __table_args__ = (
        Index("fk_alert_rule_created_by", "created_by"),
        Index("idx_alert_rule_metric_enabled", "metric_type", "enabled"),
        Index("idx_alert_rule_target_enabled", "target_type", "enabled"),
        {"comment": "告警规则表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="告警规则ID")
    rule_name: Mapped[str] = mapped_column(String(128), comment="规则名称")
    metric_type: Mapped[str] = mapped_column(String(64), comment="CPU/MEMORY/DISK/LOAD/AGENT/SERVICE/CONTAINER")
    target_type: Mapped[str] = mapped_column(
        String(32), default="SERVER", server_default=text("'SERVER'"), comment="SERVER/DISK/CONTAINER/SERVICE"
    )
    severity: Mapped[str] = mapped_column(String(16), comment="WARNING/CRITICAL")
    operator: Mapped[str] = mapped_column(String(8), comment="GT/GTE/LT/LTE/EQ")
    threshold: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="数值阈值")
    duration_seconds: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), default=0, server_default=text("0"), comment="持续异常时间，单位：秒"
    )
    recovery_threshold: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="恢复阈值，可为空")
    enabled: Mapped[int] = mapped_column(TINYINT, default=1, server_default=text("1"), comment="是否启用")
    description: Mapped[str | None] = mapped_column(String(500), comment="规则描述")
    created_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_alert_rule_created_by"),
        comment="创建人",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )

    events: Mapped[list[AlertEvent]] = relationship("AlertEvent", back_populates="rule")


class AlertEvent(Base):
    __tablename__ = "alert_event"
    __table_args__ = (
        UniqueConstraint("alert_key", "is_active", name="uk_alert_event_active_key"),
        Index("fk_alert_event_acknowledged_by", "acknowledged_by"),
        Index("idx_alert_event_rule_id", "rule_id"),
        Index("idx_alert_event_server_status", "server_id", "status"),
        Index("idx_alert_event_status_time", "status", "created_at"),
        {"comment": "告警事件表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="告警事件ID")
    rule_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("alert_rule.id", name="fk_alert_event_rule"),
        comment="告警规则ID",
    )
    server_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("ops_server.id", name="fk_alert_event_server"),
        comment="服务器ID",
    )
    resource_type: Mapped[str] = mapped_column(
        String(32), default="SERVER", server_default=text("'SERVER'"), comment="资源类型"
    )
    resource_id: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="资源ID")
    alert_key: Mapped[str] = mapped_column(String(255), comment="告警指纹，用于活动告警去重")
    metric_type: Mapped[str] = mapped_column(String(64), comment="指标类型")
    severity: Mapped[str] = mapped_column(String(16), comment="WARNING/CRITICAL")
    status: Mapped[str] = mapped_column(
        String(24), default="PENDING", server_default=text("'PENDING'"), comment="PENDING/FIRING/ACKNOWLEDGED/RESOLVED"
    )
    is_active: Mapped[int | None] = mapped_column(
        TINYINT,
        Computed(
            "CASE WHEN status IN ('PENDING', 'FIRING', 'ACKNOWLEDGED') THEN 1 ELSE NULL END",
            persisted=True,
        ),
        comment="活动告警标记，用于唯一约束",
    )
    first_fired_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="首次触发时间")
    last_fired_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="最近触发时间")
    acknowledged_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_alert_event_acknowledged_by"),
        comment="确认人",
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="确认时间")
    resolved_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="恢复时间")
    current_value: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="当前指标值")
    threshold_value: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="触发阈值")
    message: Mapped[str] = mapped_column(String(500), comment="告警消息")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )

    rule: Mapped[AlertRule] = relationship("AlertRule", back_populates="events")
    server: Mapped[OpsServer | None] = relationship("OpsServer")
    acknowledged_by_user: Mapped[SysUser | None] = relationship("SysUser", foreign_keys=[acknowledged_by])
    logs: Mapped[list[AlertEventLog]] = relationship("AlertEventLog", back_populates="event")


class AlertEventLog(Base):
    __tablename__ = "alert_event_log"
    __table_args__ = (
        Index("fk_alert_event_log_operator", "operator_id"),
        Index("idx_alert_event_log_event_time", "event_id", "created_at"),
        {"comment": "告警状态变化日志表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="告警事件日志ID")
    event_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("alert_event.id", name="fk_alert_event_log_event"),
        comment="告警事件ID",
    )
    old_status: Mapped[str | None] = mapped_column(String(24), comment="原状态")
    new_status: Mapped[str] = mapped_column(String(24), comment="新状态")
    current_value: Mapped[float | None] = mapped_column(Numeric(12, 4), comment="事件值")
    message: Mapped[str | None] = mapped_column(String(500), comment="状态变化说明")
    operator_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_alert_event_log_operator"),
        comment="操作人，系统操作可为空",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )

    event: Mapped[AlertEvent] = relationship("AlertEvent", back_populates="logs")
    operator: Mapped[SysUser | None] = relationship("SysUser")
