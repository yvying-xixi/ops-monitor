"""Dashboard 汇总接口集成测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import MonitorServerMetric
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _create_server(db, code, ip, agent_status="ONLINE"):
    server = ServerService(db).create_server(
        ServerCreate(server_code=code, hostname=code, ip_address=ip)
    )
    server.agent_status = agent_status
    db.flush()
    return server


def _add_metric(db, server_id, cpu, memory, disk):
    db.add(
        MonitorServerMetric(
            server_id=server_id,
            collected_at=_utcnow(),
            cpu_usage=cpu,
            memory_usage=memory,
            disk_usage=disk,
        )
    )
    db.flush()


def test_dashboard_overview(client, db, admin_headers):
    online = _create_server(db, "web-01", "10.0.0.1", "ONLINE")
    warn = _create_server(db, "web-02", "10.0.0.2", "WARNING")
    _create_server(db, "web-03", "10.0.0.3", "OFFLINE")
    _add_metric(db, online.id, cpu=50.0, memory=60.0, disk=70.0)
    _add_metric(db, warn.id, cpu=80.0, memory=90.0, disk=95.0)

    resp = client.get("/api/v1/dashboard/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["server_stats"]["total"] == 3
    assert data["server_stats"]["ONLINE"] == 1
    assert data["server_stats"]["WARNING"] == 1
    assert data["server_stats"]["OFFLINE"] == 1

    assert data["avg_usage"]["cpu"] == 65.0  # (50+80)/2，离线无指标不计入
    assert data["avg_usage"]["memory"] == 75.0

    servers = {s["server"]["server_code"]: s for s in data["servers"]}
    assert servers["web-01"]["latest"]["cpu_usage"] == 50.0
    assert servers["web-03"]["latest"] is None
