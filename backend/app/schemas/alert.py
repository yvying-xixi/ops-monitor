"""告警中心相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

METRIC_TYPES = ("CPU", "MEMORY", "DISK", "LOAD", "AGENT")
SEVERITIES = ("WARNING", "CRITICAL")
OPERATORS = ("GT", "GTE", "LT", "LTE", "EQ")


class RuleCreate(BaseModel):
    """创建告警规则请求体。"""

    rule_name: str = Field(..., min_length=1, max_length=128, description="规则名称")
    metric_type: str = Field(..., description="CPU/MEMORY/DISK/LOAD/AGENT")
    severity: str = Field("WARNING", description="WARNING/CRITICAL")
    operator: str = Field("GT", description="GT/GTE/LT/LTE/EQ")
    threshold: float | None = Field(None, description="数值阈值（LOAD 为 CPU 核数倍数）")
    duration_seconds: int = Field(0, ge=0, description="持续异常时间（秒）")
    recovery_threshold: float | None = Field(None, description="恢复阈值，为空则回到阈值以下恢复")
    enabled: int = Field(1, ge=0, le=1, description="是否启用")
    description: str | None = Field(None, max_length=500, description="规则描述")


class RuleUpdate(BaseModel):
    """更新告警规则请求体，全部字段可选。"""

    rule_name: str | None = Field(None, min_length=1, max_length=128)
    metric_type: str | None = None
    severity: str | None = None
    operator: str | None = None
    threshold: float | None = None
    duration_seconds: int | None = Field(None, ge=0)
    recovery_threshold: float | None = None
    enabled: int | None = Field(None, ge=0, le=1)
    description: str | None = None


class RuleOut(BaseModel):
    """告警规则响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_name: str
    metric_type: str
    target_type: str
    severity: str
    operator: str
    threshold: float | None
    duration_seconds: int
    recovery_threshold: float | None
    enabled: int
    description: str | None
    created_at: datetime


class AlertEventOut(BaseModel):
    """告警事件响应模型（含规则与服务器信息）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    rule_name: str | None = None
    server_id: int | None = None
    server_hostname: str | None = None
    metric_type: str
    severity: str
    status: str
    current_value: float | None
    threshold_value: float | None
    message: str
    first_fired_at: datetime | None
    last_fired_at: datetime | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime


class AlertEventLogOut(BaseModel):
    """告警状态日志响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    old_status: str | None
    new_status: str
    current_value: float | None
    message: str | None
    created_at: datetime
