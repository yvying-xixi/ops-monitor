"""安全工具单元测试：密码哈希与 JWT 签发/校验。"""

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.exceptions import AppException, ErrorCode


def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hash_is_randomized():
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_create_and_decode_token():
    token = create_access_token(user_id=42)
    assert decode_access_token(token) == 42


def test_decode_invalid_token_raises():
    with pytest.raises(AppException) as exc_info:
        decode_access_token("not-a-jwt-token")
    assert exc_info.value.code == ErrorCode.UNAUTHORIZED
    assert exc_info.value.http_status == 401


def test_decode_expired_token_raises():
    token = jwt.encode(
        {"sub": "1", "exp": 0},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(AppException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.code == ErrorCode.UNAUTHORIZED
