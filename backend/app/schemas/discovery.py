"""服务器发现相关请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiscoveryScanRequest(BaseModel):
    """只读扫描请求体。"""

    cidr: str = Field(..., max_length=64, description="待扫描网段，须在允许白名单内")
    port: int | None = Field(None, ge=1, le=65535, description="探测端口，默认 SSH 端口")


class DiscoveryHost(BaseModel):
    """发现的主机。"""

    ip: str = Field(..., description="IP 地址")
    port: int = Field(..., description="开放端口")
    banner: str | None = Field(None, description="端口 banner（如 SSH 版本）")
