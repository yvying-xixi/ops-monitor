"""Agent 配置加载：读取 config/config.yaml 并校验。"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """服务端连接配置。"""

    url: str = Field(..., description="服务端地址")
    token: str = Field(..., min_length=1, description="Agent 注册凭证（明文）")
    server_code: str = Field(..., min_length=1, description="服务器唯一编码")


class CollectConfig(BaseModel):
    """采集与上报周期配置。"""

    heartbeat_interval: int = Field(30, ge=5, description="心跳周期（秒）")
    metrics_interval: int = Field(10, ge=2, description="指标采集周期（秒）")
    assets_interval: int = Field(60, ge=10, description="资产/服务同步周期（秒）")
    task_poll_interval: int = Field(5, ge=2, description="任务轮询周期（秒）")
    retry_max_seconds: int = Field(60, ge=1, description="退避重试封顶（秒）")
    connect_timeout: float = Field(5.0, gt=0, description="连接超时（秒）")
    request_timeout: float = Field(10.0, gt=0, description="请求超时（秒）")
    services: list[str] = Field(
        default_factory=lambda: ["nginx", "docker", "ssh"],
        description="需要监控与受控管理的服务白名单",
    )


class LogConfig(BaseModel):
    """日志配置。"""

    level: str = Field("INFO", description="日志级别")
    file: str | None = Field(None, description="日志文件路径，为空时输出到标准输出")


class AgentConfig(BaseModel):
    """Agent 总配置。"""

    server: ServerConfig
    collect: CollectConfig = Field(default_factory=CollectConfig)
    log: LogConfig = Field(default_factory=LogConfig)


def load_config(path: str | None = None) -> AgentConfig:
    """从 YAML 文件加载 Agent 配置。

    Args:
        path: 配置文件路径，默认使用 `config/config.yaml`。

    Returns:
        校验后的 AgentConfig 对象。
    """
    if path is None:
        path = str(Path(__file__).resolve().parent / "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AgentConfig(**data)
