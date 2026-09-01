"""告警中心接口集成测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import create_role, create_user_with_password

from app.models import AlertRule, MonitorServerMetric
from app.repositories import AlertRuleRepository, UserRepository
from app.schemas.server import ServerCreate
from app.services.alert_engine import AlertEngine
from app.services.server_service import ServerService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_server(db, code="web-01"):
    return ServerService(db).create_server(
        ServerCreate(server_code=code, hostname=code, ip_address="10.0.0.1")
    )


def _make_rule(db, metric_type="CPU", severity="WARNING", threshold=80.0):
    return AlertRuleRepository(db).create(
        AlertRule(
            rule_name=f"{metric_type}-{severity}-{threshold}",
            metric_type=metric_type,
            target_type="SERVER",
            severity=severity,
            operator="GT",
            threshold=threshold,
            duration_seconds=0,
            enabled=1,
        )
    )


def _make_active_event(db, server):
    """构造一条 FIRING 告警事件。"""
    rule = _make_rule(db)
    db.add(
        MonitorServerMetric(server_id=server.id, collected_at=_utcnow(), cpu_usage=90.0)
    )
    db.flush()
    AlertEngine(db).evaluate_all()
    AlertEngine(db).evaluate_all()  # → FIRING
    return rule


def test_list_rules(client, admin_headers):
    resp = client.get("/api/v1/alerts/rules", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_create_rule_admin_only(client, db):
    # 普通用户创建规则 → 403
    role = create_role(db, "NORMAL_USER")
    user = create_user_with_password(db, "normal-user")
    UserRepository(db).set_roles(user.id, [role.id])
    token = client.post(
        "/api/v1/auth/login", json={"username": "normal-user", "password": "secret123"}
    ).json()["data"]["access_token"]
    resp = client.post(
        "/api/v1/alerts/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={"rule_name": "x", "metric_type": "CPU", "threshold": 50},
    )
    assert resp.status_code == 403


def test_create_rule_and_duplicate(client, admin_headers):
    payload = {"rule_name": "内存过高", "metric_type": "MEMORY", "severity": "WARNING", "threshold": 80}
    assert client.post("/api/v1/alerts/rules", headers=admin_headers, json=payload).status_code == 201
    resp = client.post("/api/v1/alerts/rules", headers=admin_headers, json=payload)
    assert resp.status_code == 409
    assert resp.json()["code"] == 40905


def test_update_and_delete_rule(client, db, admin_headers):
    rule = _make_rule(db, metric_type="DISK", threshold=85.0)
    resp = client.put(
        f"/api/v1/alerts/rules/{rule.id}", headers=admin_headers, json={"threshold": 90}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["threshold"] == 90
    assert client.delete(f"/api/v1/alerts/rules/{rule.id}", headers=admin_headers).status_code == 200


def test_event_ack_and_resolve(client, db, admin_headers):
    server = _make_server(db)
    _make_active_event(db, server)
    events = client.get("/api/v1/alerts", headers=admin_headers, params={"active": True}).json()["data"]
    assert events["total"] == 1
    event_id = events["items"][0]["id"]

    resp = client.post(f"/api/v1/alerts/{event_id}/ack", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ACKNOWLEDGED"

    resp = client.post(f"/api/v1/alerts/{event_id}/resolve", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "RESOLVED"

    # 已恢复后 ack → 400
    assert client.post(f"/api/v1/alerts/{event_id}/ack", headers=admin_headers).status_code == 400


def test_event_detail_with_logs(client, db, admin_headers):
    server = _make_server(db)
    _make_active_event(db, server)
    event_id = client.get("/api/v1/alerts", headers=admin_headers).json()["data"]["items"][0]["id"]
    resp = client.get(f"/api/v1/alerts/{event_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["event"]["status"] == "FIRING"
    assert len(data["logs"]) >= 1


def test_normal_user_cannot_ack(client, db, admin_headers):
    server = _make_server(db)
    _make_active_event(db, server)
    event_id = client.get("/api/v1/alerts", headers=admin_headers).json()["data"]["items"][0]["id"]

    role = create_role(db, "NORMAL_USER")
    user = create_user_with_password(db, "viewer")
    UserRepository(db).set_roles(user.id, [role.id])
    token = client.post(
        "/api/v1/auth/login", json={"username": "viewer", "password": "secret123"}
    ).json()["data"]["access_token"]
    resp = client.post(
        f"/api/v1/alerts/{event_id}/ack", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


def test_dashboard_active_alerts(client, db, admin_headers):
    server = _make_server(db)
    _make_active_event(db, server)
    resp = client.get("/api/v1/dashboard/overview", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["active_alerts"] == 1
