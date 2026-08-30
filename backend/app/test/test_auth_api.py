"""登录接口集成测试。"""

from __future__ import annotations

from app.core.security import hash_password
from app.models import SysUser
from app.repositories import UserRepository


def _create_user(db, username="alice", password="secret123", status=1):
    repo = UserRepository(db)
    return repo.create(
        SysUser(username=username, password_hash=hash_password(password), status=status)
    )


def test_login_success(client, db):
    _create_user(db, "alice", "secret123")
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 7200


def test_login_updates_last_login(client, db):
    user = _create_user(db, "bob", "secret123")
    resp = client.post("/api/v1/auth/login", json={"username": "bob", "password": "secret123"})
    assert resp.status_code == 200
    db.refresh(user)
    assert user.last_login_at is not None


def test_login_wrong_password(client, db):
    _create_user(db, "alice", "secret123")
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong-pass"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 40101


def test_login_unknown_user(client, db):
    resp = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 40101


def test_login_disabled_user(client, db):
    _create_user(db, "disabled", "secret123", status=0)
    resp = client.post("/api/v1/auth/login", json={"username": "disabled", "password": "secret123"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 40102


def test_login_validation_error(client):
    resp = client.post("/api/v1/auth/login", json={"username": "alice"})
    assert resp.status_code == 400
    assert resp.json()["code"] == 40000


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"db": True, "redis": True}
