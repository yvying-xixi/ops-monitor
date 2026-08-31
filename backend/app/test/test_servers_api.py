"""服务器管理接口集成测试（需 SYSTEM_ADMIN）。"""

from __future__ import annotations

from sqlalchemy import select

from app.models import OpsAgentToken
from app.repositories import ServerRepository
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _create_server(db, **overrides):
    data = {
        "server_code": "web-01",
        "hostname": "web-01",
        "ip_address": "10.0.0.1",
    }
    data.update(overrides)
    return ServerService(db).create_server(ServerCreate(**data))


def test_create_server(client, admin_headers):
    resp = client.post(
        "/api/v1/servers",
        headers=admin_headers,
        json={"server_code": "web-01", "hostname": "web-01", "ip_address": "10.0.0.1"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["server_code"] == "web-01"
    assert data["agent_status"] == "OFFLINE"


def test_list_servers_requires_admin(client, db):
    _create_server(db)
    assert client.get("/api/v1/servers").status_code == 401


def test_create_duplicate_server_code(client, db, admin_headers):
    _create_server(db)
    resp = client.post(
        "/api/v1/servers",
        headers=admin_headers,
        json={"server_code": "web-01", "hostname": "x", "ip_address": "10.0.0.2"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40903


def test_list_servers(client, db, admin_headers):
    _create_server(db, server_code="web-01", ip_address="10.0.0.1")
    _create_server(db, server_code="db-01", ip_address="10.0.0.2")
    resp = client.get("/api/v1/servers", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 2


def test_generate_agent_token_stores_hash_only(client, db, admin_headers):
    server = _create_server(db)
    resp = client.post(f"/api/v1/servers/{server.id}/agent-token", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["token"]
    assert data["token_prefix"] == data["token"][:8]

    records = db.scalars(
        select(OpsAgentToken).where(OpsAgentToken.server_id == server.id)
    ).all()
    assert len(records) == 1
    assert records[0].token_hash != data["token"]
    assert data["token"] not in records[0].token_hash
