"""pytest 共享夹具：事务隔离的数据库会话、TestClient 与认证辅助。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.security import hash_password
from app.main import app
from app.models import SysRole, SysUser
from app.repositories import RoleRepository, UserRepository


@pytest.fixture()
def db():
    """提供事务隔离的数据库会话。

    外层开启连接事务，会话以 savepoint 模式加入，Service 层的 commit
    仅提交 savepoint；测试结束后回滚外层事务，数据不落库。
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
    )
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    """返回覆盖 get_db 的 TestClient。

    操作审计中间件关闭（避免写真实库），且不触发 lifespan（种子数据不写入）。
    """

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    original = settings.OPERATION_LOG_ENABLED
    settings.OPERATION_LOG_ENABLED = False
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        settings.OPERATION_LOG_ENABLED = original
        test_client.close()


def create_role(db, role_code: str) -> SysRole:
    """创建角色（不存在时）。"""
    repo = RoleRepository(db)
    role = repo.get_by_code(role_code)
    if role is None:
        role = repo.create(SysRole(role_code=role_code, role_name=role_code))
    return role


def create_user_with_password(db, username: str, password: str = "secret123") -> SysUser:
    """创建启用状态用户并返回。"""
    return UserRepository(db).create(
        SysUser(username=username, password_hash=hash_password(password), status=1)
    )


@pytest.fixture()
def admin_headers(client, db):
    """创建 SYSTEM_ADMIN 用户并登录，返回 Bearer 认证头。"""
    role = create_role(db, "SYSTEM_ADMIN")
    user = create_user_with_password(db, "test-admin")
    UserRepository(db).set_roles(user.id, [role.id])
    resp = client.post(
        "/api/v1/auth/login", json={"username": "test-admin", "password": "secret123"}
    )
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
