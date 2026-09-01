"""告警仓储：规则、事件与状态日志。"""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import AlertEvent, AlertEventLog, AlertRule
from app.repositories.base import BaseRepository


class AlertRuleRepository(BaseRepository[AlertRule]):
    """告警规则仓储。"""

    model = AlertRule

    def get_enabled(self) -> list[AlertRule]:
        """查询全部启用规则（告警引擎遍历用）。"""
        return self.list_all(enabled=1)

    def get_by_name(self, rule_name: str) -> AlertRule | None:
        return self.get_by(rule_name=rule_name)


class AlertEventRepository(BaseRepository[AlertEvent]):
    """告警事件仓储。"""

    model = AlertEvent

    def get_active_by_alert_key(self, alert_key: str) -> AlertEvent | None:
        """查询指定告警指纹的活动告警（用于去重）。"""
        stmt = select(AlertEvent).where(
            AlertEvent.alert_key == alert_key,
            AlertEvent.is_active.isnot(None),
        )
        return self.db.scalars(stmt).first()

    def list_events(
        self,
        page: int = 1,
        page_size: int = 20,
        *,
        status: str | None = None,
        severity: str | None = None,
        server_id: int | None = None,
        active: bool | None = None,
    ) -> tuple[int, list[AlertEvent]]:
        """分页查询告警事件。

        Args:
            page: 页码。
            page_size: 每页数量。
            status: 状态过滤（PENDING/FIRING/ACKNOWLEDGED/RESOLVED）。
            severity: 级别过滤（WARNING/CRITICAL）。
            server_id: 服务器过滤。
            active: 仅活动告警（is_active 非空）。

        Returns:
            元组 (total, items)。
        """
        filters: dict = {}
        if status:
            filters["status"] = status
        if severity:
            filters["severity"] = severity
        if server_id is not None:
            filters["server_id"] = server_id

        base_stmt = select(AlertEvent).where(*[
            getattr(AlertEvent, key) == value for key, value in filters.items()
        ])
        if active is not None:
            if active:
                base_stmt = base_stmt.where(AlertEvent.is_active.isnot(None))
            else:
                base_stmt = base_stmt.where(AlertEvent.is_active.is_(None))

        total = self.db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
        stmt = (
            base_stmt.order_by(AlertEvent.last_fired_at.desc(), AlertEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return total, list(self.db.scalars(stmt).all())

    def count_active(self) -> int:
        """统计当前活动告警数（Dashboard 用）。"""
        stmt = select(func.count()).select_from(AlertEvent).where(AlertEvent.is_active.isnot(None))
        return self.db.scalar(stmt) or 0


class AlertEventLogRepository(BaseRepository[AlertEventLog]):
    """告警状态日志仓储。"""

    model = AlertEventLog

    def record(
        self,
        *,
        event_id: int,
        old_status: str | None,
        new_status: str,
        current_value,
        message: str,
        operator_id: int | None = None,
    ) -> AlertEventLog:
        return self.create(
            AlertEventLog(
                event_id=event_id,
                old_status=old_status,
                new_status=new_status,
                current_value=current_value,
                message=message,
                operator_id=operator_id,
            )
        )
