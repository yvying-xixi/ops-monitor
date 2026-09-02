"""服务器资产管理相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServerCreate(BaseModel):
    """创建服务器请求体。"""

    server_code: str = Field(..., min_length=1, max_length=64, description="服务器唯一编码")
    hostname: str = Field(..., min_length=1, max_length=128, description="主机名")
    ip_address: str = Field(..., min_length=1, max_length=64, description="IP 地址")
    ssh_port: int = Field(22, ge=1, le=65535, description="SSH 端口")
    remark: str | None = Field(None, max_length=500, description="备注")


class ServerOut(BaseModel):
    """服务器信息响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="服务器 ID")
    server_code: str = Field(..., description="服务器唯一编码")
    hostname: str = Field(..., description="主机名")
    ip_address: str = Field(..., description="IP 地址")
    ssh_port: int = Field(..., description="SSH 端口")
    os_name: str | None = Field(None, description="操作系统名称")
    os_version: str | None = Field(None, description="操作系统版本")
    agent_version: str | None = Field(None, description="Agent 版本")
    agent_status: str = Field(..., description="ONLINE/WARNING/OFFLINE/UNKNOWN")
    last_heartbeat_at: datetime | None = Field(None, description="最后心跳时间")
    registered_at: datetime | None = Field(None, description="注册时间")
    status: int = Field(..., description="资产状态：0停用，1启用")
    remark: str | None = Field(None, description="备注")
    created_at: datetime = Field(..., description="创建时间")


class AgentTokenResponse(BaseModel):
    """Agent 注册凭证响应模型（明文仅返回一次）。"""

    id: int = Field(..., description="Token 记录 ID")
    token_name: str = Field(..., description="Token 名称")
    token_prefix: str = Field(..., description="Token 前缀，用于识别")
    token: str = Field(..., description="Token 明文，仅此一次展示，请妥善保存")
    created_at: datetime = Field(..., description="创建时间")


class ServerServiceOut(BaseModel):
    """服务资产响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="服务资产 ID")
    service_name: str = Field(..., description="服务名称")
    display_name: str | None = Field(None, description="展示名称")
    service_type: str = Field(..., description="SYSTEMD/DOCKER/CUSTOM")
    is_whitelisted: int = Field(..., description="是否允许受控操作")
    is_critical: int = Field(..., description="是否关键服务")
    current_status: str | None = Field(None, description="RUNNING/STOPPED/FAILED/UNKNOWN")
    last_checked_at: datetime | None = Field(None, description="最后检查时间")


class ServiceWhitelistUpdate(BaseModel):
    """更新服务白名单请求体。"""

    is_whitelisted: int = Field(..., ge=0, le=1, description="0 禁止受控操作，1 允许")
