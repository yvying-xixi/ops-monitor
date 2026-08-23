"""
数据库、Redis连通性测试工具，用于pytest单元测试
"""

import redis
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine


def test_mariadb_connection():
    """测试MariaDB数据库连通性，执行SELECT 1校验连接是否正常"""
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_redis_ping():
    """redis ping心跳检测，验证网络连通"""
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    assert client.ping() is True


def test_redis_read_write():
    """完整读写测试：写入随机key、读取、最后清理key，校验读写权限正常"""
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    key = f"test:conn:conn-{__import__('uuid').uuid4()}"
    try:
        client.set(key, "hello")
        assert client.get(key) == "hello"
    finally:
        client.delete(key)
