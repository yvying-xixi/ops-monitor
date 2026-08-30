"""pytest 共享夹具：事务隔离的数据库会话与 TestClient。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app


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
    """返回覆盖 get_db 的 TestClient（不触发 lifespan，种子数据不写入）。"""

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()
        test_client.close()
