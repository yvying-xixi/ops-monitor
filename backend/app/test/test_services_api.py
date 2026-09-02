"""服务状态上报与服务管理接口测试。"""

from __future__ import annotations

from sqlalchemy import select

from app.models import OpsServerService
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _make_server_and_token(db):
    server = ServerService(db).create_server(
        ServerCreate(server_code="svc-01", hostname="svc-01", ip_address="10.0.0.5")
    )
    token = ServerService(db).generate_agent_token(server.id).token
    return server, token


def test_sync_services(client, db):
    server, token = _make_server_and_token(db)
    resp = client.post(
        "/api/v1/agent/services",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "server_id": server.id,
            "services": [
                {"service_name": "nginx", "current_status": "RUNNING"},
                {"service_name": "docker", "current_status": "STOPPED"},
            ],
        },
    )
    assert resp.status_code == 200
    services = db.scalars(
        select(OpsServerService).where(OpsServerService.server_id == server.id)
    ).all()
    statuses = {s.service_name: s.current_status for s in services}
    assert statuses["nginx"] == "RUNNING"
    assert statuses["docker"] == "STOPPED"
    assert all(s.is_whitelisted == 1 for s in services)


def test_sync_services_updates_status(client, db):
    server, token = _make_server_and_token(db)
    payload = {
        "server_id": server.id,
        "services": [{"service_name": "nginx", "current_status": "RUNNING"}],
    }
    assert client.post("/api/v1/agent/services", headers={"Authorization": f"Bearer {token}"}, json=payload).status_code == 200
    payload["services"][0]["current_status"] = "FAILED"
    assert client.post("/api/v1/agent/services", headers={"Authorization": f"Bearer {token}"}, json=payload).status_code == 200

    services = db.scalars(select(OpsServerService)).all()
    assert len(services) == 1  # 幂等，不重复
    assert services[0].current_status == "FAILED"


def test_list_services(client, db, admin_headers):
    server, token = _make_server_and_token(db)
    client.post(
        "/api/v1/agent/services",
        headers={"Authorization": f"Bearer {token}"},
        json={"server_id": server.id, "services": [{"service_name": "nginx", "current_status": "RUNNING"}]},
    )
    resp = client.get(f"/api/v1/servers/{server.id}/services", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"][0]["service_name"] == "nginx"


def test_whitelist_toggle(client, db, admin_headers):
    server, token = _make_server_and_token(db)
    client.post(
        "/api/v1/agent/services",
        headers={"Authorization": f"Bearer {token}"},
        json={"server_id": server.id, "services": [{"service_name": "nginx", "current_status": "RUNNING"}]},
    )
    service = db.scalars(select(OpsServerService)).first()
    resp = client.put(
        f"/api/v1/servers/{server.id}/services/{service.id}/whitelist",
        headers=admin_headers,
        json={"is_whitelisted": 0},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_whitelisted"] == 0
