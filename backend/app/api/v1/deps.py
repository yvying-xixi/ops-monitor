"""鉴权依赖：当前用户、角色与接口权限校验。"""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.exceptions import AppException, ErrorCode
from app.models import SysUser
from app.repositories import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> SysUser:
    """解析 Bearer Token 并加载当前用户。

    Args:
        token: JWT 字符串。
        db: 数据库会话。

    Returns:
        当前登录用户对象。

    Raises:
        AppException: Token 无效（40100）、用户不存在（40100）、账号禁用（40102）。
    """
    user_id = decode_access_token(token)
    user = UserRepository(db).get(user_id)
    if user is None:
        raise AppException(ErrorCode.UNAUTHORIZED, "用户不存在或已被删除", http_status=401)
    if user.status != 1:
        raise AppException(ErrorCode.ACCOUNT_DISABLED, "账号已禁用", http_status=401)
    return user


def get_current_roles(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """获取当前用户的角色编码列表。

    Args:
        current_user: 当前用户。
        db: 数据库会话。

    Returns:
        角色编码列表。
    """
    roles = UserRepository(db).get_roles_by_user(current_user.id)
    return [role.role_code for role in roles]


def require_roles(*role_codes: str):
    """生成接口权限校验依赖，要求当前用户具有任一指定角色。

    Args:
        *role_codes: 允许的角色编码集合。

    Returns:
        FastAPI 依赖函数，校验失败时抛出 403。
    """

    def dependency(
        current_user: SysUser = Depends(get_current_user),
        user_roles: list[str] = Depends(get_current_roles),
    ) -> SysUser:
        if not set(role_codes) & set(user_roles):
            raise AppException(ErrorCode.FORBIDDEN, "无权限执行该操作", http_status=403)
        return current_user

    return dependency
