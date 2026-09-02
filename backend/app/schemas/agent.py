"""Agent 协议相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Agent 注册请求体。"""

    server_code: str = Field(..., max_length=64, description="服务器唯一编码")
    token: str = Field(..., min_length=1, description="Agent 注册凭证")
    hostname: str = Field("", max_length=128, description="主机名")
    os_name: str | None = Field(None, max_length=128, description="操作系统名称")
    os_version: str | None = Field(None, max_length=128, description="操作系统版本")
    kernel_version: str | None = Field(None, max_length=128, description="内核版本")
    architecture: str | None = Field(None, max_length=32, description="系统架构")
    cpu_model: str | None = Field(None, max_length=255, description="CPU 型号")
    cpu_cores: int | None = Field(None, ge=0, description="CPU 逻辑核心数")
    memory_total_bytes: int | None = Field(None, ge=0, description="内存总量（字节）")
    disk_total_bytes: int | None = Field(None, ge=0, description="磁盘总量（字节）")
    agent_version: str | None = Field(None, max_length=32, description="Agent 版本")


class HeartbeatRequest(BaseModel):
    """Agent 心跳请求体。"""

    server_id: int | None = Field(None, description="服务器 ID，用于交叉校验")
    agent_version: str | None = Field(None, max_length=32, description="Agent 版本")
    timestamp: datetime | None = Field(None, description="Agent 侧时间")


class MetricsRequest(BaseModel):
    """Agent 指标上报请求体。"""

    server_id: int | None = Field(None, description="服务器 ID，用于交叉校验")
    timestamp: datetime = Field(..., description="采集时间")
    cpu_usage: float | None = Field(None, ge=0, le=100, description="CPU 使用率（%）")
    memory_usage: float | None = Field(None, ge=0, le=100, description="内存使用率（%）")
    memory_used_bytes: int | None = Field(None, ge=0, description="已使用内存（字节）")
    disk_usage: float | None = Field(None, ge=0, le=100, description="磁盘使用率（%）")
    network_in_bytes: int | None = Field(None, ge=0, description="累计入站字节数")
    network_out_bytes: int | None = Field(None, ge=0, description="累计出站字节数")
    load_1m: float | None = Field(None, ge=0, description="1 分钟 Load")
    load_5m: float | None = Field(None, ge=0, description="5 分钟 Load")
    load_15m: float | None = Field(None, ge=0, description="15 分钟 Load")
    tcp_connections: int | None = Field(None, ge=0, description="TCP 连接数")
    uptime_seconds: int | None = Field(None, ge=0, description="系统运行时长（秒）")


class DiskAsset(BaseModel):
    """磁盘资产。"""

    device_name: str = Field(..., max_length=128, description="设备名称")
    mount_point: str | None = Field(None, max_length=255, description="挂载点")
    filesystem: str | None = Field(None, max_length=64, description="文件系统")
    total_bytes: int | None = Field(None, ge=0, description="磁盘总量（字节）")


class NetworkAsset(BaseModel):
    """网卡资产。"""

    interface_name: str = Field(..., max_length=128, description="网卡名称")
    mac_address: str | None = Field(None, max_length=64, description="MAC 地址")
    ip_address: str | None = Field(None, max_length=64, description="网卡 IP")


class AssetsRequest(BaseModel):
    """Agent 资产同步请求体。"""

    server_id: int | None = Field(None, description="服务器 ID，用于交叉校验")
    timestamp: datetime | None = Field(None, description="Agent 侧时间")
    disks: list[DiskAsset] = Field(default_factory=list, description="磁盘列表")
    networks: list[NetworkAsset] = Field(default_factory=list, description="网卡列表")


class ServiceStatus(BaseModel):
    """服务状态上报项。"""

    service_name: str = Field(..., max_length=64, description="服务名称")
    current_status: str = Field(..., description="RUNNING/STOPPED/FAILED/UNKNOWN")


class ServicesRequest(BaseModel):
    """Agent 服务状态同步请求体。"""

    server_id: int | None = Field(None, description="服务器 ID，用于交叉校验")
    timestamp: datetime | None = Field(None, description="Agent 侧时间")
    services: list[ServiceStatus] = Field(default_factory=list, description="服务状态列表")
