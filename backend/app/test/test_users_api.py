"""用户管理接口集成测试（需 SYSTEM_ADMIN 权限）。"""

from __future__ import annotations

from conftest import create_role

from app.core.security import hash_password
from app.models import SysUser
from app.repositories import UserRepository


def _create_user(db, username="alice"):
    repo = UserRepository(db)
    return repo.create(
        SysUser(username=username, password_hash=hash_password("secret123"))
    )


def test_create_user(client, admin_headers):
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "newuser", "password": "secret123", "nickname": "新用户"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["username"] == "newuser"
    assert data["nickname"] == "新用户"
    assert data["id"] is not None


def test_create_user_with_roles(client, db, admin_headers):
    role = create_role(db, "OPS_ENGINEER")
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "withroles", "password": "secret123", "role_ids": [role.id]},
    )
    assert resp.status_code == 201
    roles = resp.json()["data"]["roles"]
    assert [r["role_code"] for r in roles] == ["OPS_ENGINEER"]


def test_create_duplicate_username(client, db, admin_headers):
    _create_user(db, "dup")
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "dup", "password": "secret123"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40901


def test_create_user_invalid_role(client, admin_headers):
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "badrole", "password": "secret123", "role_ids": [999999]},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 40402


def test_list_users_pagination(client, db, admin_headers):
    for i in range(5):
        _create_user(db, f"user{i}")
    resp = client.get(
        "/api/v1/users", headers=admin_headers, params={"page": 1, "page_size": 2}
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 6  # 5 个测试用户 + admin_headers 夹具创建的 test-admin
    assert len(body["items"]) == 2


def test_get_user(client, db, admin_headers):
    user = _create_user(db, "getme")
    resp = client.get(f"/api/v1/users/{user.id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "getme"


def test_get_user_not_found(client, admin_headers):
    resp = client.get("/api/v1/users/999999", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == 40401


def test_update_user(client, db, admin_headers):
    user = _create_user(db, "updateme")
    resp = client.put(
        f"/api/v1/users/{user.id}",
        headers=admin_headers,
        json={"nickname": "改名", "status": 0},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["nickname"] == "改名"
    assert data["status"] == 0


def test_update_user_duplicate_email(client, db, admin_headers):
    _create_user(db, "first")
    second = _create_user(db, "second")
    resp = client.put(
        f"/api/v1/users/{second.id}",
        headers=admin_headers,
        json={"email": "a@example.com"},
    )
    assert resp.status_code == 200
    resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "third", "password": "secret123", "email": "a@example.com"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40902


def test_delete_user(client, db, admin_headers):
    user = _create_user(db, "deleteme")
    resp = client.delete(f"/api/v1/users/{user.id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert client.get(f"/api/v1/users/{user.id}", headers=admin_headers).status_code == 404
