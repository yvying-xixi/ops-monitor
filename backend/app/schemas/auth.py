"""认证相关请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求体。"""

    username: str = Field(..., min_length=1, max_length=64, description="登录用户名")
    password: str = Field(..., min_length=1, max_length=128, description="登录密码")


class TokenResponse(BaseModel):
    """登录成功返回的 Token 信息。"""

    access_token: str = Field(..., description="JWT Access Token")
    token_type: str = Field("bearer", description="Token 类型")
    expires_in: int = Field(..., description="有效期，单位：秒")
