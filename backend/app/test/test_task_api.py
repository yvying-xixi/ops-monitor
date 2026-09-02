"""任务接口集成测试：创建/确认/取消/白名单/权限。"""

from __future__ import annotations

from conftest import create_role, create_user_with_password

from app.repositories import UserRepository
from app.repositories.server_repository import ServiceRepository
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _make_server(db, code="web-01", service="nginx", whitelisted=1):
    server = ServerService(db).create_server(
        ServerCreate(server_code=code, hostname=code, ip_address="10.0.0.1")
    )
    ServiceRepository(db).upsert_status(server.id, service, "RUNNING")
    if whitelisted == 0:
        svc = ServiceRepository(db).get_by_server_service(server.id, service)
        ServiceRepository(db).set_whitelist(svc, 0)
    return server


def _check_payload(server_id):
    return {
        "task_name": "检查 nginx",
        "task_type": "SERVICE_CHECK",
        "service_name": "nginx",
        "server_ids": [server_id],
    }


def test_create_check_task_immediate(client, db, admin_headers):
    server = _make_server(db)
    resp = client.post("/api/v1/tasks", headers=admin_headers, json=_check_payload(server.id))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "PENDING"  # STATUS 免确认
    assert data["confirmation_required"] == 0


def test_create_action_task_requires_confirm(client, db, admin_headers):
    server = _make_server(db)
    resp = client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "task_name": "重启 nginx",
            "task_type": "SERVICE_ACTION",
            "action": "RESTART",
            "service_name": "nginx",
            "server_ids": [server.id],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "CREATED"  # 需确认
    assert data["confirmation_required"] == 1
    task_id = data["id"]

    resp = client.post(f"/api/v1/tasks/{task_id}/confirm", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "PENDING"


def test_create_action_non_whitelisted_service_forbidden(client, db, admin_headers):
    server = _make_server(db, service="docker", whitelisted=0)
    resp = client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "task_name": "启 docker",
            "task_type": "SERVICE_ACTION",
            "action": "START",
            "service_name": "docker",
            "server_ids": [server.id],
        },
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40301


def test_create_action_service_not_reported_forbidden(client, db, admin_headers):
    server = _make_server(db, service="nginx")
    resp = client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "task_name": "操 ssh",
            "task_type": "SERVICE_ACTION",
            "action": "START",
            "service_name": "ssh",  # 未上报到资产表
            "server_ids": [server.id],
        },
    )
    assert resp.status_code == 403


def test_create_invalid_action(client, db, admin_headers):
    server = _make_server(db)
    resp = client.post(
        "/api/v1/tasks",
        headers=admin_headers,
        json={
            "task_name": "x",
            "task_type": "SERVICE_CHECK",
            "action": "START",  # 与类型不符
            "server_ids": [server.id],
        },
    )
    assert resp.status_code == 400


def test_normal_user_forbidden(client, db):
    role = create_role(db, "NORMAL_USER")
    user = create_user_with_password(db, "normal")
    UserRepository(db).set_roles(user.id, [role.id])
    token = client.post(
        "/api/v1/auth/login", json={"username": "normal", "password": "secret123"}
    ).json()["data"]["access_token"]
    resp = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_cancel_task(client, db, admin_headers):
    server = _make_server(db)
    task_id = client.post("/api/v1/tasks", headers=admin_headers, json=_check_payload(server.id)).json()["data"]["id"]
    resp = client.post(f"/api/v1/tasks/{task_id}/cancel", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CANCELLED"


def test_task_detail_with_executions(client, db, admin_headers):
    server = _make_server(db)
    task_id = client.post("/api/v1/tasks", headers=admin_headers, json=_check_payload(server.id)).json()["data"]["id"]
    resp = client.get(f"/api/v1/tasks/{task_id}", headers=admin_headers)
    assert resp.status_code == 200
    detail = resp.json()["data"]
    assert detail["task"]["id"] == task_id
    assert len(detail["executions"]) == 1
