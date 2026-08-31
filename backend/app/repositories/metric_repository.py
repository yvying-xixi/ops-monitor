"""监控指标仓储。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models import MonitorServerMetric
from app.repositories.base import BaseRepository


class MetricRepository(BaseRepository[MonitorServerMetric]):
    """服务器监控指标仓储。"""

    model = MonitorServerMetric

    def record(self, metric: MonitorServerMetric) -> MonitorServerMetric:
        return self.create(metric)

    def get_latest(self, server_id: int) -> MonitorServerMetric | None:
        stmt = (
            select(MonitorServerMetric)
            .where(MonitorServerMetric.server_id == server_id)
            .order_by(MonitorServerMetric.collected_at.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def get_history(
        self,
        server_id: int,
        start: datetime,
        end: datetime,
        *,
        limit: int = 500,
    ) -> list[MonitorServerMetric]:
        stmt = (
            select(MonitorServerMetric)
            .where(
                MonitorServerMetric.server_id == server_id,
                MonitorServerMetric.collected_at >= start,
                MonitorServerMetric.collected_at <= end,
            )
            .order_by(MonitorServerMetric.collected_at.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
