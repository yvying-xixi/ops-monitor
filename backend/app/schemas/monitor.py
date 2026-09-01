"""监控中心相关请求与响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MetricBucketValue(BaseModel):
    """单个指标在时间桶内的聚合值。"""

    avg: float | None = Field(None, description="平均值")
    max: float | None = Field(None, description="最大值")
    min: float | None = Field(None, description="最小值")


class MetricBucket(BaseModel):
    """时间桶聚合点。"""

    time: datetime = Field(..., description="桶起始时间")
    cpu_usage: MetricBucketValue | None = None
    memory_usage: MetricBucketValue | None = None
    disk_usage: MetricBucketValue | None = None
    load_1m: MetricBucketValue | None = None
    load_5m: MetricBucketValue | None = None
    load_15m: MetricBucketValue | None = None
    tcp_connections: MetricBucketValue | None = None
    network_in_rate: float | None = Field(None, description="入站速率（MB/s）")
    network_out_rate: float | None = Field(None, description="出站速率（MB/s）")


class MetricSummary(BaseModel):
    """指标聚合响应。"""

    range: str = Field(..., description="时间范围标识")
    bucket_seconds: int = Field(..., description="桶宽（秒）")
    start: datetime = Field(..., description="起始时间")
    end: datetime = Field(..., description="结束时间")
    points: list[MetricBucket] = Field(default_factory=list, description="聚合点列表")
