"""监控中心接口集成测试：latest/history/summary/assets。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import MonitorServerMetric, OpsServerDisk, OpsServerNetwork
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _create_server(db, code="mon-01", ip="10.0.0.10"):
    return ServerService(db).create_server(
        ServerCreate(server_code=code, hostname=code, ip_address=ip)
    )


def _add_metric(db, server_id, collected_at, **values):
    data = {"server_id": server_id, "collected_at": collected_at}
    data.update(values)
    db.add(MonitorServerMetric(**data))
    db.flush()
    return data


def test_latest_returns_newest(client, db, admin_headers):
    server = _create_server(db)
    now = _utcnow()
    _add_metric(db, server.id, now - timedelta(minutes=5), cpu_usage=10.0)
    _add_metric(db, server.id, now - timedelta(minutes=1), cpu_usage=80.5)
    resp = client.get(f"/api/v1/servers/{server.id}/metrics/latest", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["metric"]["cpu_usage"] == 80.5


def test_latest_no_metric(client, db, admin_headers):
    server = _create_server(db)
    resp = client.get(f"/api/v1/servers/{server.id}/metrics/latest", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["metric"] is None


def test_history_pagination(client, db, admin_headers):
    server = _create_server(db)
    now = _utcnow()
    for i in range(5):
        _add_metric(db, server.id, now - timedelta(minutes=10 - i), cpu_usage=float(i))
    resp = client.get(
        f"/api/v1/servers/{server.id}/metrics/history",
        headers=admin_headers,
        params={
            "start": (now - timedelta(hours=1)).isoformat(),
            "end": now.isoformat(),
            "page": 1,
            "page_size": 2,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_summary_aggregates_and_network_rate(client, db, admin_headers):
    server = _create_server(db)
    now = _utcnow()
    mb = 1024 * 1024
    # 桶宽 60s：t0 与 t0+60s 两个桶
    _add_metric(db, server.id, now - timedelta(minutes=2), cpu_usage=10.0, network_in_bytes=0)
    _add_metric(db, server.id, now - timedelta(minutes=1), cpu_usage=90.0, network_in_bytes=60 * mb)
    resp = client.get(
        f"/api/v1/servers/{server.id}/metrics/summary",
        headers=admin_headers,
        params={"range": "1h"},
    )
    assert resp.status_code == 200
    points = resp.json()["data"]["points"]
    assert len(points) == 2
    # CPU 聚合 avg/max/min
    assert points[0]["cpu_usage"]["avg"] == 10.0
    assert points[1]["cpu_usage"]["max"] == 90.0
    # 网络差分速率：60MB / 60s = 1 MB/s（第二桶）
    assert points[0]["network_in_rate"] == 0
    assert points[1]["network_in_rate"] == 1.0


def test_summary_invalid_range(client, db, admin_headers):
    server = _create_server(db)
    resp = client.get(
        f"/api/v1/servers/{server.id}/metrics/summary",
        headers=admin_headers,
        params={"range": "2d"},
    )
    assert resp.status_code == 400


def test_assets(client, db, admin_headers):
    server = _create_server(db)
    db.add(OpsServerDisk(server_id=server.id, device_name="/dev/sda1", mount_point="/", total_bytes=100))
    db.add(OpsServerNetwork(server_id=server.id, interface_name="eth0", ip_address="10.0.0.10"))
    db.flush()
    resp = client.get(f"/api/v1/servers/{server.id}/assets", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["disks"][0]["mount_point"] == "/"
    assert data["networks"][0]["interface_name"] == "eth0"


def test_monitor_requires_auth(client, db):
    server = _create_server(db)
    resp = client.get(f"/api/v1/servers/{server.id}/metrics/latest")
    assert resp.status_code == 401
