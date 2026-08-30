"""用户管理接口集成测试。"""

from __future__ import annotations

from app.core.security import hash_password
from app.models import SysRole, SysUser
from app.repositories import RoleRepository, UserRepository


def _create_role(db, code="OPS_ENGINEER"):
    repo = RoleRepository(db)
    return repo.create(SysRole(role_code=code, role_name=code))


def _create_user(db, username="alice"):
    repo = UserRepository(db)
    return repo.create(
        SysUser(username=username, password_hash=hash_password("secret123"))
    )


def test_create_user(client):
    resp = client.post(
        "/api/v1/users",
        json={"username": "newuser", "password": "secret123", "nickname": "新用户"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["username"] == "newuser"
    assert data["nickname"] == "新用户"
    assert data["id"] is not None


def test_create_user_with_roles(client, db):
    role = _create_role(db)
    resp = client.post(
        "/api/v1/users",
        json={"username": "withroles", "password": "secret123", "role_ids": [role.id]},
    )
    assert resp.status_code == 201
    roles = resp.json()["data"]["roles"]
    assert [r["role_code"] for r in roles] == ["OPS_ENGINEER"]


def test_create_duplicate_username(client, db):
    _create_user(db, "dup")
    resp = client.post("/api/v1/users", json={"username": "dup", "password": "secret123"})
    assert resp.status_code == 409
    assert resp.json()["code"] == 40901


def test_create_user_invalid_role(client):
    resp = client.post(
        "/api/v1/users",
        json={"username": "badrole", "password": "secret123", "role_ids": [999999]},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 40402


def test_list_users_pagination(client, db):
    for i in range(5):
        _create_user(db, f"user{i}")
    resp = client.get("/api/v1/users", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_get_user(client, db):
    user = _create_user(db, "getme")
    resp = client.get(f"/api/v1/users/{user.id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "getme"


def test_get_user_not_found(client):
    resp = client.get("/api/v1/users/999999")
    assert resp.status_code == 404
    assert resp.json()["code"] == 40401


def test_update_user(client, db):
    user = _create_user(db, "updateme")
    resp = client.put(
        f"/api/v1/users/{user.id}", json={"nickname": "改名", "status": 0}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["nickname"] == "改名"
    assert data["status"] == 0


def test_update_user_duplicate_email(client, db):
    _create_user(db, "first")
    second = _create_user(db, "second")
    resp = client.put(
        f"/api/v1/users/{second.id}",
        json={"email": "a@example.com"},
    )
    assert resp.status_code == 200
    resp = client.post(
        "/api/v1/users", json={"username": "third", "password": "secret123", "email": "a@example.com"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40902


def test_delete_user(client, db):
    user = _create_user(db, "deleteme")
    resp = client.delete(f"/api/v1/users/{user.id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert client.get(f"/api/v1/users/{user.id}").status_code == 404
