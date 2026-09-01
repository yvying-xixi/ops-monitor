"""告警引擎：定时扫描规则与指标，驱动告警状态机。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AlertEvent, OpsServer
from app.repositories import (
    AlertEventLogRepository,
    AlertEventRepository,
    AlertRuleRepository,
    MetricRepository,
    ServerRepository,
)

logger = logging.getLogger(__name__)

# metric_type → monitor_server_metric 字段映射
METRIC_FIELD_MAP = {
    "CPU": "cpu_usage",
    "MEMORY": "memory_usage",
    "DISK": "disk_usage",
    "LOAD": "load_1m",
}

OPERATORS = ("GT", "GTE", "LT", "LTE", "EQ")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AlertEngine:
    """告警引擎。

    状态机：PENDING → FIRING → ACKNOWLEDGED → RESOLVED。
    每个 (rule, server, metric_type) 通过 `alert_key` 维护一条活动告警，
    配合数据库生成列 `is_active` 唯一键实现去重。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.rule_repo = AlertRuleRepository(db)
        self.event_repo = AlertEventRepository(db)
        self.log_repo = AlertEventLogRepository(db)
        self.server_repo = ServerRepository(db)
        self.metric_repo = MetricRepository(db)

    def evaluate_all(self) -> int:
        """执行一轮完整评估。

        Returns:
            本轮新增的告警数量。
        """
        rules = self.rule_repo.get_enabled()
        servers = self.server_repo.list_active()
        if not rules or not servers:
            return 0

        latest_map = self.metric_repo.get_latest_map([s.id for s in servers])
        now = _utcnow()
        created = 0

        for rule in rules:
            for server in servers:
                value = self._get_value(rule, server, latest_map.get(server.id), now)
                if value is None:
                    continue
                threshold = self._effective_threshold(rule, server)
                if self._compare(value, rule.operator, threshold):
                    if self._handle_violation(rule, server, value, threshold, now):
                        created += 1
                else:
                    self._handle_recovery(rule, server, value, now)

        self.db.commit()
        return created

    def _get_value(self, rule, server: OpsServer, metric, now: datetime) -> float | None:
        """按规则类型取值。"""
        if rule.metric_type == "AGENT":
            if server.last_heartbeat_at is None:
                return None
            return (now - server.last_heartbeat_at).total_seconds()

        field = METRIC_FIELD_MAP.get(rule.metric_type)
        if field is None or metric is None:
            return None
        value = getattr(metric, field)
        return float(value) if value is not None else None

    def _effective_threshold(self, rule, server: OpsServer) -> float | None:
        """计算有效阈值：LOAD 规则将 threshold 视为 CPU 核数倍数。"""
        if rule.threshold is None:
            return None
        if rule.metric_type == "LOAD":
            cores = server.cpu_cores or 1
            return round(float(rule.threshold) * cores, 4)
        return float(rule.threshold)

    @staticmethod
    def _compare(value: float, operator: str, threshold: float | None) -> bool:
        """执行阈值比较。"""
        if threshold is None:
            return False
        if operator == "GTE":
            return value >= threshold
        if operator == "LT":
            return value < threshold
        if operator == "LTE":
            return value <= threshold
        if operator == "EQ":
            return value == threshold
        return value > threshold  # 默认 GT

    def _handle_violation(self, rule, server, value, threshold, now) -> bool:
        """处理超阈值：创建 PENDING 或升级 FIRING。返回是否新增告警。"""
        alert_key = self._alert_key(rule, server)
        event = self.event_repo.get_active_by_alert_key(alert_key)

        if event is None:
            event = AlertEvent(
                rule_id=rule.id,
                server_id=server.id,
                resource_type=rule.target_type,
                resource_id=server.id,
                alert_key=alert_key,
                metric_type=rule.metric_type,
                severity=rule.severity,
                status="PENDING",
                first_fired_at=now,
                last_fired_at=now,
                current_value=value,
                threshold_value=threshold,
                message=f"{rule.rule_name} 触发：当前值 {self._fmt(value)}，阈值 {self._fmt(threshold)}",
            )
            self.event_repo.create(event)
            self.log_repo.record(
                event_id=event.id, old_status=None, new_status="PENDING",
                current_value=value, message="检测到异常，进入待确认",
            )
            return True

        event.last_fired_at = now
        event.current_value = value
        if event.status == "PENDING":
            elapsed = (now - event.first_fired_at).total_seconds()
            if elapsed >= (rule.duration_seconds or 0):
                self._transition(event, "FIRING", value, message="达到持续异常时长，触发告警")
        return False

    def _handle_recovery(self, rule, server, value, now) -> None:
        """指标恢复时解除活动告警。"""
        event = self.event_repo.get_active_by_alert_key(self._alert_key(rule, server))
        if event is not None and self._is_recovered(rule, value):
            event.resolved_at = now
            self._transition(event, "RESOLVED", value, message="指标恢复正常，告警解除")

    def _is_recovered(self, rule, value: float) -> bool:
        """判断是否满足恢复条件。"""
        if rule.recovery_threshold is not None:
            return value <= float(rule.recovery_threshold)
        return not self._compare(value, rule.operator, rule.threshold)

    def _transition(self, event, new_status, value, *, message: str) -> None:
        old_status = event.status
        event.status = new_status
        event.current_value = value
        self.db.flush()
        self.log_repo.record(
            event_id=event.id, old_status=old_status, new_status=new_status,
            current_value=value, message=message,
        )

    @staticmethod
    def _alert_key(rule, server: OpsServer) -> str:
        return f"{rule.id}:{server.id}:{rule.metric_type}"

    @staticmethod
    def _fmt(value) -> str:
        return f"{value:.2f}" if isinstance(value, float) else str(value)
