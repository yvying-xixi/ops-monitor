"""用户管理相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleBrief(BaseModel):
    """角色摘要信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="角色 ID")
    role_code: str = Field(..., description="角色编码")
    role_name: str = Field(..., description="角色名称")


class UserCreate(BaseModel):
    """创建用户请求体。"""

    username: str = Field(
        ..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_]+$", description="登录用户名"
    )
    password: str = Field(..., min_length=6, max_length=128, description="登录密码")
    nickname: str | None = Field(None, max_length=64, description="用户昵称")
    email: str | None = Field(None, max_length=128, description="邮箱")
    phone: str | None = Field(None, max_length=32, description="手机号")
    role_ids: list[int] = Field(default_factory=list, description="角色 ID 列表")


class UserUpdate(BaseModel):
    """更新用户请求体，全部字段可选。"""

    password: str | None = Field(None, min_length=6, max_length=128, description="新密码")
    nickname: str | None = Field(None, max_length=64, description="用户昵称")
    email: str | None = Field(None, max_length=128, description="邮箱")
    phone: str | None = Field(None, max_length=32, description="手机号")
    status: int | None = Field(None, ge=0, le=1, description="状态：0禁用，1启用")
    role_ids: list[int] | None = Field(None, description="角色 ID 列表")


class UserOut(BaseModel):
    """用户信息响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="登录用户名")
    nickname: str | None = Field(None, description="用户昵称")
    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    status: int = Field(..., description="状态：0禁用，1启用")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    roles: list[RoleBrief] = Field(default_factory=list, description="角色列表")
