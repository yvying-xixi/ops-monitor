"""安全工具：密码哈希与 JWT 签发/校验。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.exceptions.app_exception import AppException
from app.exceptions.error_codes import ErrorCode

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """使用 bcrypt 对明文密码进行哈希。

    Args:
        password: 明文密码。

    Returns:
        bcrypt 哈希字符串。
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配。

    Args:
        plain_password: 待校验的明文密码。
        hashed_password: 存储的 bcrypt 哈希。

    Returns:
        匹配返回 True，否则返回 False。
    """
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int) -> str:
    """为用户签发 JWT Access Token。

    Args:
        user_id: 用户 ID，作为 JWT 的 `sub` 声明。

    Returns:
        签发的 JWT 字符串。
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """解析并校验 JWT，返回用户 ID。

    Args:
        token: JWT 字符串。

    Returns:
        用户 ID。

    Raises:
        AppException: Token 缺失、过期或签名非法时抛出 401。
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED,
            message="Token 无效或已过期",
            http_status=401,
        ) from exc
