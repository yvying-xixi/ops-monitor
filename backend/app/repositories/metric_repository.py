"""监控指标仓储。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.models import MonitorServerMetric
from app.repositories.base import BaseRepository

# summary 聚合的数值字段
SUMMARY_NUMERIC_FIELDS = [
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "load_1m",
    "load_5m",
    "load_15m",
    "tcp_connections",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[int, list[MonitorServerMetric]]:
        """分页查询原始历史指标。"""
        base_stmt = select(MonitorServerMetric).where(
            MonitorServerMetric.server_id == server_id,
            MonitorServerMetric.collected_at >= start,
            MonitorServerMetric.collected_at <= end,
        )
        total = self.db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
        stmt = (
            base_stmt.order_by(MonitorServerMetric.collected_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return total, list(self.db.scalars(stmt).all())

    def get_summary(
        self,
        server_id: int,
        start: datetime,
        end: datetime,
        bucket_seconds: int,
    ) -> list:
        """按时间桶聚合指标（AVG/MAX/MIN），返回原始行。

        网络累计值以桶内 MAX 作为采样，速率由服务层做相邻点差分计算。

        Returns:
            SQLAlchemy Row 列表，字段为 bucket 及各指标的 *_avg/_max/_min，
            以及 network_in_max/network_out_max。
        """
        bucket_expr = func.from_unixtime(
            func.floor(func.unix_timestamp(MonitorServerMetric.collected_at) / bucket_seconds)
            * bucket_seconds
        )
        columns = [bucket_expr.label("bucket")]
        for field in SUMMARY_NUMERIC_FIELDS:
            col = getattr(MonitorServerMetric, field)
            columns.append(func.avg(col).label(f"{field}_avg"))
            columns.append(func.max(col).label(f"{field}_max"))
            columns.append(func.min(col).label(f"{field}_min"))
        columns.append(func.max(MonitorServerMetric.network_in_bytes).label("network_in_max"))
        columns.append(func.max(MonitorServerMetric.network_out_bytes).label("network_out_max"))

        stmt = (
            select(*columns)
            .where(
                MonitorServerMetric.server_id == server_id,
                MonitorServerMetric.collected_at >= start,
                MonitorServerMetric.collected_at <= end,
            )
            .group_by(bucket_expr)
            .order_by(bucket_expr.asc())
        )
        return list(self.db.execute(stmt).all())

    def get_server_usage_avg(self) -> tuple[float | None, float | None, float | None]:
        """计算全部服务器最新指标的 CPU/内存/磁盘平均使用率。"""
        latest = (
            select(
                MonitorServerMetric.server_id,
                func.max(MonitorServerMetric.collected_at).label("latest"),
            )
            .group_by(MonitorServerMetric.server_id)
            .subquery()
        )
        stmt = (
            select(
                func.avg(MonitorServerMetric.cpu_usage),
                func.avg(MonitorServerMetric.memory_usage),
                func.avg(MonitorServerMetric.disk_usage),
            )
            .join(latest, MonitorServerMetric.server_id == latest.c.server_id)
            .where(MonitorServerMetric.collected_at == latest.c.latest)
        )
        row = self.db.execute(stmt).one()
        return (round(row[0], 2) if row[0] is not None else None,
                round(row[1], 2) if row[1] is not None else None,
                round(row[2], 2) if row[2] is not None else None)

    def get_latest_map(self, server_ids: list[int]) -> dict[int, MonitorServerMetric]:
        """批量查询多台服务器的最新指标，返回 {server_id: metric}。"""
        if not server_ids:
            return {}
        latest = (
            select(
                MonitorServerMetric.server_id,
                func.max(MonitorServerMetric.collected_at).label("latest"),
            )
            .where(MonitorServerMetric.server_id.in_(server_ids))
            .group_by(MonitorServerMetric.server_id)
            .subquery()
        )
        stmt = (
            select(MonitorServerMetric)
            .join(latest, MonitorServerMetric.server_id == latest.c.server_id)
            .where(MonitorServerMetric.collected_at == latest.c.latest)
        )
        return {m.server_id: m for m in self.db.scalars(stmt).all()}

    def delete_older_than(self, days: int) -> int:
        """删除早于保留期的历史指标。"""
        cutoff = _utcnow() - timedelta(days=days)
        result = self.db.execute(
            delete(MonitorServerMetric).where(MonitorServerMetric.collected_at < cutoff)
        )
        return result.rowcount or 0
