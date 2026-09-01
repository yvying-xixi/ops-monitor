"""认证相关接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.schemas.auth import LoginRequest
from app.schemas.user import UserOut
from app.services.auth_service import AuthService
from app.utils.request import get_client_ip
from app.utils.response import success

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/me", summary="当前用户信息")
def me(
    current_user=Depends(get_current_user),
):
    """获取当前登录用户信息（含角色）。"""
    return success(data=UserOut.model_validate(current_user).model_dump())


@router.post("/login", summary="用户登录", description="校验账号密码，签发 JWT Access Token。")
def login(
    request: LoginRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """用户登录接口。

    Args:
        request: 登录请求体。
        http_request: 原始请求，用于提取 IP、UA 与请求 ID。
        db: 数据库会话。

    Returns:
        统一响应，data 为 TokenResponse。
    """
    service = AuthService(db)
    token = service.login(
        request.username,
        request.password,
        ip=get_client_ip(http_request),
        user_agent=http_request.headers.get("user-agent"),
        request_id=getattr(http_request.state, "request_id", None),
    )
    return success(data=token.model_dump())
