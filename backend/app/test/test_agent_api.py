"""Agent 协议接口集成测试：注册、心跳、指标、资产。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import OpsAgentHeartbeat, MonitorServerMetric, OpsServerDisk, OpsServerNetwork
from app.repositories import ServerRepository
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def agent_ctx(db):
    """创建服务器并生成 Agent Token，返回 (server, plaintext_token)。"""
    from app.services.server_service import ServerService

    server = ServerService(db).create_server(
        ServerCreate(server_code="web-01", hostname="web-01", ip_address="10.0.0.1")
    )
    result = ServerService(db).generate_agent_token(server.id)
    return server, result.token


@pytest.fixture()
def agent_headers(agent_ctx):
    server, token = agent_ctx
    return {"Authorization": f"Bearer {token}"}


def _register_payload(**overrides):
    data = {
        "server_code": "web-01",
        "token": "PLACEHOLDER",
        "hostname": "web-01",
        "os_name": "Ubuntu",
        "os_version": "22.04",
        "kernel_version": "5.15.0",
        "architecture": "x86_64",
        "cpu_model": "Intel Xeon",
        "cpu_cores": 4,
        "memory_total_bytes": 8 * 1024**3,
        "disk_total_bytes": 100 * 1024**3,
        "agent_version": "1.0.0",
    }
    data.update(overrides)
    return data


def test_register_success(client, db, agent_ctx):
    server, token = agent_ctx
    payload = _register_payload(token=token)
    resp = client.post("/api/v1/agent/register", json=payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["server_id"] == server.id

    db.refresh(server)
    assert server.agent_status == "ONLINE"
    assert server.os_name == "Ubuntu"
    assert server.cpu_cores == 4
    assert server.registered_at is not None


def test_register_invalid_token(client, db):
    payload = _register_payload(token="wrong-token")
    resp = client.post("/api/v1/agent/register", json=payload)
    assert resp.status_code == 401
    assert resp.json()["code"] == 40103


def test_register_mismatched_server_code(client, db, agent_ctx):
    server, token = agent_ctx
    payload = _register_payload(token=token, server_code="other-01")
    resp = client.post("/api/v1/agent/register", json=payload)
    assert resp.status_code == 401


def test_heartbeat_requires_token(client, db):
    assert client.post("/api/v1/agent/heartbeat", json={}).status_code == 401


def test_heartbeat_success(client, db, agent_headers, agent_ctx):
    server, _ = agent_ctx
    resp = client.post(
        "/api/v1/agent/heartbeat",
        headers=agent_headers,
        json={"server_id": server.id, "agent_version": "1.0.0"},
    )
    assert resp.status_code == 200
    db.refresh(server)
    assert server.last_heartbeat_at is not None
    heartbeats = db.scalars(
        select(OpsAgentHeartbeat).where(OpsAgentHeartbeat.server_id == server.id)
    ).all()
    assert len(heartbeats) == 1


def test_metrics_success(client, db, agent_headers, agent_ctx):
    server, _ = agent_ctx
    resp = client.post(
        "/api/v1/agent/metrics",
        headers=agent_headers,
        json={
            "server_id": server.id,
            "timestamp": _utcnow().isoformat(),
            "cpu_usage": 42.5,
            "memory_usage": 61.2,
            "load_1m": 1.5,
            "tcp_connections": 128,
            "uptime_seconds": 3600,
        },
    )
    assert resp.status_code == 200
    rows = db.scalars(
        select(MonitorServerMetric).where(MonitorServerMetric.server_id == server.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].cpu_usage == 42.5


def test_metrics_rejects_future_timestamp(client, agent_headers, agent_ctx):
    server, _ = agent_ctx
    future = _utcnow() + timedelta(hours=2)
    resp = client.post(
        "/api/v1/agent/metrics",
        headers=agent_headers,
        json={"server_id": server.id, "timestamp": future.isoformat(), "cpu_usage": 10.0},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40001


def test_assets_sync(client, db, agent_headers, agent_ctx):
    server, _ = agent_ctx
    payload = {
        "server_id": server.id,
        "disks": [
            {"device_name": "/dev/sda1", "mount_point": "/", "filesystem": "ext4", "total_bytes": 100000},
            {"device_name": "/dev/sdb1", "mount_point": "/data", "filesystem": "xfs", "total_bytes": 200000},
        ],
        "networks": [{"interface_name": "eth0", "mac_address": "aa:bb", "ip_address": "10.0.0.1"}],
    }
    resp = client.post("/api/v1/agent/assets", headers=agent_headers, json=payload)
    assert resp.status_code == 200
    assert len(db.scalars(select(OpsServerDisk).where(OpsServerDisk.server_id == server.id)).all()) == 2
    assert len(db.scalars(select(OpsServerNetwork).where(OpsServerNetwork.server_id == server.id)).all()) == 1

    # 缺失项被删除：仅保留 /data
    resp = client.post(
        "/api/v1/agent/assets",
        headers=agent_headers,
        json={"server_id": server.id, "disks": [payload["disks"][1]]},
    )
    assert resp.status_code == 200
    disks = db.scalars(select(OpsServerDisk).where(OpsServerDisk.server_id == server.id)).all()
    assert [d.mount_point for d in disks] == ["/data"]


def test_agent_server_mismatch_rejected(client, agent_headers, agent_ctx, db):
    server, _ = agent_ctx
    other = ServerService(db).create_server(
        ServerCreate(server_code="db-01", hostname="db-01", ip_address="10.0.0.2")
    )
    resp = client.post(
        "/api/v1/agent/heartbeat",
        headers=agent_headers,
        json={"server_id": other.id},
    )
    assert resp.status_code == 401
