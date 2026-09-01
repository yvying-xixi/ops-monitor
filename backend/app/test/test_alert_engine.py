"""告警引擎测试：状态机流转、去重、AGENT/LOAD 语义。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import AlertEvent, AlertRule, MonitorServerMetric
from app.repositories import AlertEventRepository, AlertRuleRepository
from app.schemas.server import ServerCreate
from app.services.alert_engine import AlertEngine
from app.services.server_service import ServerService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_server(db, code="web-01", cores=4):
    server = ServerService(db).create_server(
        ServerCreate(server_code=code, hostname=code, ip_address="10.0.0.1")
    )
    server.cpu_cores = cores
    db.flush()
    return server


def _make_rule(db, metric_type="CPU", severity="WARNING", operator="GT", threshold=80.0, duration=0):
    return AlertRuleRepository(db).create(
        AlertRule(
            rule_name=f"{metric_type}-{severity}",
            metric_type=metric_type,
            target_type="SERVER",
            severity=severity,
            operator=operator,
            threshold=threshold,
            duration_seconds=duration,
            enabled=1,
        )
    )


def _add_metric(db, server_id, cpu=None, memory=None, load_1m=None):
    db.add(
        MonitorServerMetric(
            server_id=server_id,
            collected_at=_utcnow(),
            cpu_usage=cpu,
            memory_usage=memory,
            load_1m=load_1m,
        )
    )
    db.flush()


def test_violation_creates_pending_then_firing(db):
    server = _make_server(db)
    rule = _make_rule(db)
    _add_metric(db, server.id, cpu=90.0)

    created = AlertEngine(db).evaluate_all()
    assert created == 1
    event = AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:CPU")
    assert event is not None
    assert event.status == "PENDING"

    # 第二次评估：持续达标 → FIRING
    AlertEngine(db).evaluate_all()
    db.expire_all()
    event = AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:CPU")
    assert event.status == "FIRING"


def test_no_duplicate_active_event(db):
    server = _make_server(db)
    rule = _make_rule(db)
    _add_metric(db, server.id, cpu=90.0)
    for _ in range(3):
        AlertEngine(db).evaluate_all()
    events = AlertEventRepository(db).list_events(1, 100, active=True)
    assert events[0] == 1  # 仅一条活动告警
    assert len(events[1]) == 1


def test_duration_delay(db):
    server = _make_server(db)
    rule = _make_rule(db, duration=300)
    _add_metric(db, server.id, cpu=90.0)
    AlertEngine(db).evaluate_all()
    event = AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:CPU")
    assert event.status == "PENDING"  # 未到 300s 仍 PENDING

    # 回拨首次触发时间，模拟已持续 10 分钟
    event.first_fired_at = _utcnow() - timedelta(minutes=10)
    db.flush()
    AlertEngine(db).evaluate_all()
    db.expire_all()
    event = AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:CPU")
    assert event.status == "FIRING"


def test_recovery_resolves(db):
    server = _make_server(db)
    rule = _make_rule(db)
    _add_metric(db, server.id, cpu=90.0)
    AlertEngine(db).evaluate_all()
    AlertEngine(db).evaluate_all()  # → FIRING

    _add_metric(db, server.id, cpu=10.0)  # 恢复
    AlertEngine(db).evaluate_all()
    db.expire_all()
    assert AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:CPU") is None
    assert AlertEventRepository(db).count_active() == 0
    # 历史事件 RESOLVED
    total, items = AlertEventRepository(db).list_events(1, 100)
    assert total == 1 and items[0].status == "RESOLVED"


def test_agent_offline_alert(db):
    server = _make_server(db)
    rule = _make_rule(db, metric_type="AGENT", threshold=90)
    server.last_heartbeat_at = _utcnow() - timedelta(seconds=120)
    db.flush()
    created = AlertEngine(db).evaluate_all()
    assert created == 1
    event = AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:AGENT")
    assert event is not None
    assert float(event.current_value) == pytest.approx(120.0, abs=1)


def test_load_threshold_multiplies_cores(db):
    server = _make_server(db, cores=4)
    rule = _make_rule(db, metric_type="LOAD", threshold=1.0)
    _add_metric(db, server.id, load_1m=5.0)  # 5 > 4×1.0 → 触发
    AlertEngine(db).evaluate_all()
    assert AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:LOAD") is not None

    # 换低负载
    AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:LOAD").status = "RESOLVED"
    db.flush()
    _add_metric(db, server.id, load_1m=3.0)  # 3 < 4 → 不触发
    AlertEngine(db).evaluate_all()
    event = AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:LOAD")
    assert event is None or event.status == "RESOLVED"


def test_acknowledged_keeps_active(db):
    server = _make_server(db)
    rule = _make_rule(db)
    _add_metric(db, server.id, cpu=90.0)
    AlertEngine(db).evaluate_all()
    event = AlertEventRepository(db).get_active_by_alert_key(f"{rule.id}:{server.id}:CPU")
    event.status = "ACKNOWLEDGED"
    db.flush()
    AlertEngine(db).evaluate_all()  # 仍超阈值，不应新建
    assert AlertEventRepository(db).count_active() == 1
