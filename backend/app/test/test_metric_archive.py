"""指标归档测试：原始指标聚合到日表并清理。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import MonitorServerMetric, MonitorServerMetricDaily
from app.repositories import MetricRepository
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _make_server(db):
    return ServerService(db).create_server(
        ServerCreate(server_code="arch-01", hostname="arch-01", ip_address="10.7.0.1")
    )


def test_aggregate_and_cleanup_metrics(db):
    server = _make_server(db)
    repo = MetricRepository(db)

    day1 = _utcnow() - timedelta(days=10)
    day2 = _utcnow() - timedelta(days=9)
    repo.record(
        MonitorServerMetric(
            server_id=server.id,
            collected_at=day1.replace(hour=1, minute=0, second=0, microsecond=0),
            cpu_usage=10,
            memory_usage=20,
            disk_usage=30,
            load_1m=1,
            tcp_connections=5,
        )
    )
    repo.record(
        MonitorServerMetric(
            server_id=server.id,
            collected_at=day1.replace(hour=2, minute=0, second=0, microsecond=0),
            cpu_usage=30,
            memory_usage=40,
            disk_usage=50,
            load_1m=3,
            tcp_connections=15,
        )
    )
    repo.record(
        MonitorServerMetric(
            server_id=server.id,
            collected_at=day2.replace(hour=1, minute=0, second=0, microsecond=0),
            cpu_usage=50,
            memory_usage=60,
            disk_usage=70,
            load_1m=5,
            tcp_connections=25,
        )
    )
    db.flush()

    cutoff = _utcnow() - timedelta(days=7)
    assert repo.aggregate_daily(cutoff) == 2

    rows = list(
        db.scalars(
            select(MonitorServerMetricDaily).where(MonitorServerMetricDaily.server_id == server.id)
        ).all()
    )
    daily = {row.metric_date: row for row in rows}
    day1_row = daily[day1.date()]
    assert float(day1_row.cpu_usage_avg) == 20.0
    assert float(day1_row.cpu_usage_max) == 30.0
    assert day1_row.sample_count == 2
    assert daily[day2.date()].sample_count == 1

    # 幂等：重复聚合不产生新行
    assert repo.aggregate_daily(cutoff) == 2

    # 清理原始与超期聚合
    assert repo.delete_older_than(7) == 3
    assert repo.delete_daily_before(5) == 2
