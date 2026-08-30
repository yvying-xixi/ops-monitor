"""鉴权依赖测试：无 Token、无效 Token、角色权限校验。"""

from __future__ import annotations

from conftest import create_role, create_user_with_password

from app.repositories import UserRepository


def test_users_requires_token(client):
    resp = client.get("/api/v1/users")
    assert resp.status_code == 401
    assert resp.json()["code"] == 40100


def test_users_rejects_invalid_token(client):
    resp = client.get("/api/v1/users", headers={"Authorization": "Bearer invalid-token"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 40100


def test_users_forbidden_for_normal_user(client, db):
    role = create_role(db, "NORMAL_USER")
    user = create_user_with_password(db, "normal-user")
    UserRepository(db).set_roles(user.id, [role.id])
    token = client.post(
        "/api/v1/auth/login", json={"username": "normal-user", "password": "secret123"}
    ).json()["data"]["access_token"]
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["code"] == 40300


def test_users_allowed_for_admin(client, admin_headers):
    resp = client.get("/api/v1/users", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_disabled_user_token_rejected(client, db):
    role = create_role(db, "SYSTEM_ADMIN")
    user = create_user_with_password(db, "soon-disabled")
    UserRepository(db).set_roles(user.id, [role.id])
    token = client.post(
        "/api/v1/auth/login", json={"username": "soon-disabled", "password": "secret123"}
    ).json()["data"]["access_token"]

    user.status = 0
    db.commit()

    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 40102


def test_request_id_header_present(client):
    resp = client.get("/api/v1/health")
    assert "X-Request-ID" in resp.headers
    assert resp.headers["X-Request-ID"]
