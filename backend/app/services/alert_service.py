"""告警中心服务：规则管理与事件操作。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import AppException, ErrorCode
from app.models import AlertEvent, AlertEventLog, AlertRule, OpsServer
from app.repositories import (
    AlertEventLogRepository,
    AlertEventRepository,
    AlertRuleRepository,
    ServerRepository,
)
from app.schemas.alert import RuleCreate, RuleUpdate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AlertService:
    """告警中心业务逻辑，事务提交统一在此层完成。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.rule_repo = AlertRuleRepository(db)
        self.event_repo = AlertEventRepository(db)
        self.log_repo = AlertEventLogRepository(db)
        self.server_repo = ServerRepository(db)

    # ---------- 规则管理 ----------

    def list_rules(self) -> list[AlertRule]:
        return self.rule_repo.list_all()

    def get_rule(self, rule_id: int) -> AlertRule:
        rule = self.rule_repo.get(rule_id)
        if rule is None:
            raise AppException(ErrorCode.RULE_NOT_FOUND, "告警规则不存在", http_status=404)
        return rule

    def create_rule(self, data: RuleCreate, *, created_by: int | None = None) -> AlertRule:
        if self.rule_repo.get_by_name(data.rule_name):
            raise AppException(ErrorCode.RULE_NAME_EXISTS, "规则名称已存在", http_status=409)
        rule = AlertRule(
            rule_name=data.rule_name,
            metric_type=data.metric_type.upper(),
            target_type="SERVER",
            severity=data.severity.upper(),
            operator=data.operator.upper(),
            threshold=data.threshold,
            duration_seconds=data.duration_seconds,
            recovery_threshold=data.recovery_threshold,
            enabled=data.enabled,
            description=data.description,
            created_by=created_by,
        )
        self.rule_repo.create(rule)
        self.db.commit()
        return rule

    def update_rule(self, rule_id: int, data: RuleUpdate) -> AlertRule:
        rule = self.get_rule(rule_id)
        values = data.model_dump(exclude_unset=True)
        if "rule_name" in values and values["rule_name"] and values["rule_name"] != rule.rule_name:
            existing = self.rule_repo.get_by_name(values["rule_name"])
            if existing and existing.id != rule_id:
                raise AppException(ErrorCode.RULE_NAME_EXISTS, "规则名称已存在", http_status=409)
        for key in ("metric_type", "severity", "operator"):
            if key in values and values[key]:
                values[key] = values[key].upper()
        self.rule_repo.update(rule, **values)
        self.db.commit()
        return rule

    def delete_rule(self, rule_id: int) -> None:
        rule = self.get_rule(rule_id)
        self.rule_repo.delete(rule)
        self.db.commit()

    # ---------- 事件操作 ----------

    def list_events(
        self,
        page: int,
        page_size: int,
        *,
        status: str | None = None,
        severity: str | None = None,
        server_id: int | None = None,
        active: bool | None = None,
    ) -> tuple[int, list[dict]]:
        total, items = self.event_repo.list_events(
            page, page_size, status=status, severity=severity, server_id=server_id, active=active
        )
        return total, [self._event_dict(e) for e in items]

    def get_event(self, event_id: int) -> dict:
        event = self.event_repo.get(event_id)
        if event is None:
            raise AppException(ErrorCode.ALERT_EVENT_NOT_FOUND, "告警事件不存在", http_status=404)
        logs = self.db.scalars(
            select(AlertEventLog)
            .where(AlertEventLog.event_id == event_id)
            .order_by(AlertEventLog.id.asc())
        ).all()
        return {"event": self._event_dict(event), "logs": [self._log_dict(log) for log in logs]}

    def acknowledge(self, event_id: int, *, operator_id: int | None) -> dict:
        """确认告警：PENDING/FIRING/ACKNOWLEDGED → ACKNOWLEDGED。"""
        event = self._get_event_or_404(event_id)
        if event.status == "RESOLVED":
            raise AppException(ErrorCode.BAD_REQUEST, "已恢复的告警无需确认", http_status=400)
        old_status = event.status
        event.status = "ACKNOWLEDGED"
        event.acknowledged_by = operator_id
        event.acknowledged_at = _utcnow()
        self.db.flush()
        self.log_repo.record(
            event_id=event.id, old_status=old_status, new_status="ACKNOWLEDGED",
            current_value=event.current_value, message="人工确认告警", operator_id=operator_id,
        )
        self.db.commit()
        return self._event_dict(event)

    def resolve(self, event_id: int, *, operator_id: int | None) -> dict:
        """人工恢复告警：活动状态 → RESOLVED。"""
        event = self._get_event_or_404(event_id)
        if event.status == "RESOLVED":
            raise AppException(ErrorCode.BAD_REQUEST, "告警已恢复", http_status=400)
        old_status = event.status
        event.status = "RESOLVED"
        event.resolved_at = _utcnow()
        self.db.flush()
        self.log_repo.record(
            event_id=event.id, old_status=old_status, new_status="RESOLVED",
            current_value=event.current_value, message="人工恢复告警", operator_id=operator_id,
        )
        self.db.commit()
        return self._event_dict(event)

    def count_active(self) -> int:
        return self.event_repo.count_active()

    # ---------- 辅助 ----------

    def _get_event_or_404(self, event_id: int) -> AlertEvent:
        event = self.event_repo.get(event_id)
        if event is None:
            raise AppException(ErrorCode.ALERT_EVENT_NOT_FOUND, "告警事件不存在", http_status=404)
        return event

    def _event_dict(self, event: AlertEvent) -> dict:
        rule = self.rule_repo.get(event.rule_id) if event.rule_id else None
        server = self.server_repo.get(event.server_id) if event.server_id else None
        return {
            "id": event.id,
            "rule_id": event.rule_id,
            "rule_name": rule.rule_name if rule else None,
            "server_id": event.server_id,
            "server_hostname": server.hostname if server else None,
            "metric_type": event.metric_type,
            "severity": event.severity,
            "status": event.status,
            "current_value": float(event.current_value) if event.current_value is not None else None,
            "threshold_value": float(event.threshold_value) if event.threshold_value is not None else None,
            "message": event.message,
            "first_fired_at": event.first_fired_at,
            "last_fired_at": event.last_fired_at,
            "acknowledged_at": event.acknowledged_at,
            "resolved_at": event.resolved_at,
            "created_at": event.created_at,
        }

    @staticmethod
    def _log_dict(log: AlertEventLog) -> dict:
        return {
            "id": log.id,
            "event_id": log.event_id,
            "old_status": log.old_status,
            "new_status": log.new_status,
            "current_value": float(log.current_value) if log.current_value is not None else None,
            "message": log.message,
            "created_at": log.created_at,
        }
