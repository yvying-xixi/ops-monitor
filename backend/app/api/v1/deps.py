"""鉴权依赖：当前用户、角色与接口权限校验。"""

from __future__ import annotations

import time

import redis
from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import signing
from app.core.config import settings
from app.core.database import get_db
from app.core.replay import is_replayed
from app.core.security import decode_access_token
from app.exceptions import AppException, ErrorCode
from app.models import OpsAgentToken, OpsServer, SysUser
from app.repositories import AgentTokenRepository, ServerRepository, UserRepository

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


async def get_agent_server(
    request: Request,
    token: str = Depends(oauth2_scheme),
    x_agent_id: str | None = Header(None, alias="X-Agent-Id"),
    x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    x_request_id: str | None = Header(None, alias="X-Request-Id"),
    x_signature: str | None = Header(None, alias="X-Signature"),
    db: Session = Depends(get_db),
) -> OpsServer:
    """解析 Bearer Token 并加载 Agent 绑定的服务器，并按需校验请求签名。

    Agent 上报接口专用鉴权：按 Token 哈希查 `ops_agent_token`，校验有效状态后
    返回绑定服务器，并按 ADR-010 校验 Ed25519 请求签名（放宽或强制由
    `AGENT_REQUIRE_SIGNATURE` 控制）。

    Raises:
        AppException: Token 无效（40103）、服务器不存在或停用（40403）、
            签名缺失/无效/重放（40104-40107）。
    """
    _, server = await _resolve_agent(
        request,
        token,
        db,
        x_agent_id=x_agent_id,
        x_timestamp=x_timestamp,
        x_request_id=x_request_id,
        x_signature=x_signature,
    )
    return server


async def get_agent_token(
    request: Request,
    token: str = Depends(oauth2_scheme),
    x_agent_id: str | None = Header(None, alias="X-Agent-Id"),
    x_timestamp: str | None = Header(None, alias="X-Timestamp"),
    x_request_id: str | None = Header(None, alias="X-Request-Id"),
    x_signature: str | None = Header(None, alias="X-Signature"),
    db: Session = Depends(get_db),
) -> OpsAgentToken:
    """与 `get_agent_server` 相同鉴权，但返回 Token 记录（用于公钥轮换等）。"""
    token_record, _ = await _resolve_agent(
        request,
        token,
        db,
        x_agent_id=x_agent_id,
        x_timestamp=x_timestamp,
        x_request_id=x_request_id,
        x_signature=x_signature,
    )
    return token_record


async def _resolve_agent(
    request: Request,
    token: str,
    db: Session,
    *,
    x_agent_id: str | None,
    x_timestamp: str | None,
    x_request_id: str | None,
    x_signature: str | None,
) -> tuple[OpsAgentToken, OpsServer]:
    """校验 Agent Token 与请求签名，返回 (token 记录, 服务器)。"""
    token_record = AgentTokenRepository(db).authenticate(token)
    if token_record is None:
        raise AppException(ErrorCode.AGENT_UNAUTHORIZED, "Agent 凭证无效", http_status=401)
    server = ServerRepository(db).get(token_record.server_id)
    if server is None or server.status != 1:
        raise AppException(ErrorCode.SERVER_NOT_FOUND, "服务器不存在或已停用", http_status=404)

    await _verify_agent_signature(
        request,
        token_record,
        server,
        x_agent_id=x_agent_id,
        x_timestamp=x_timestamp,
        x_request_id=x_request_id,
        x_signature=x_signature,
    )
    return token_record, server


async def _verify_agent_signature(
    request: Request,
    token_record: OpsAgentToken,
    server: OpsServer,
    *,
    x_agent_id: str | None,
    x_timestamp: str | None,
    x_request_id: str | None,
    x_signature: str | None,
) -> None:
    """校验 Agent 请求签名与防重放（见 ADR-010）。"""
    if x_agent_id is None or x_timestamp is None or x_request_id is None or x_signature is None:
        if settings.AGENT_REQUIRE_SIGNATURE:
            raise AppException(ErrorCode.AGENT_SIGNATURE_MISSING, "缺少请求签名", http_status=401)
        return

    if x_agent_id != server.server_code:
        raise AppException(ErrorCode.AGENT_SIGNATURE_INVALID, "Agent 标识与凭证不匹配", http_status=401)

    try:
        timestamp = int(x_timestamp)
    except (TypeError, ValueError):
        raise AppException(ErrorCode.AGENT_TIMESTAMP_INVALID, "时间戳非法", http_status=401) from None
    if abs(int(time.time()) - timestamp) > settings.AGENT_SIGNATURE_MAX_SKEW:
        raise AppException(ErrorCode.AGENT_TIMESTAMP_INVALID, "时间戳超出允许范围", http_status=401)

    if not token_record.signing_public_key:
        if settings.AGENT_REQUIRE_SIGNATURE:
            raise AppException(ErrorCode.AGENT_SIGNATURE_INVALID, "未注册签名公钥", http_status=401)
        return

    body = await request.body()
    canonical = signing.canonical_string(
        request.method, request.url.path, x_timestamp, x_request_id, body
    )
    if not signing.verify_signature(token_record.signing_public_key, x_signature, canonical):
        raise AppException(ErrorCode.AGENT_SIGNATURE_INVALID, "请求签名无效", http_status=401)

    try:
        replayed = is_replayed(server.id, x_request_id, settings.AGENT_SIGNATURE_MAX_SKEW * 2)
    except redis.RedisError:
        if settings.AGENT_REQUIRE_SIGNATURE:
            raise AppException(
                ErrorCode.AGENT_SIGNATURE_INVALID, "重放校验服务不可用", http_status=503
            ) from None
        replayed = False
    if replayed:
        raise AppException(ErrorCode.AGENT_REQUEST_REPLAYED, "请求已重放", http_status=401)
