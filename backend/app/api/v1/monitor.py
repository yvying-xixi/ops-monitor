"""监控中心接口：指标查询与资产查看。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.schemas.monitor import MetricSummary
from app.schemas.server import ServerOut
from app.services.monitor_service import MonitorService
from app.utils.response import page, success

router = APIRouter(prefix="/servers", tags=["监控中心"])


def _metric_dict(metric):
    if metric is None:
        return None
    return {
        "id": metric.id,
        "server_id": metric.server_id,
        "collected_at": metric.collected_at,
        "cpu_usage": float(metric.cpu_usage) if metric.cpu_usage is not None else None,
        "memory_usage": float(metric.memory_usage) if metric.memory_usage is not None else None,
        "memory_used_bytes": metric.memory_used_bytes,
        "disk_usage": float(metric.disk_usage) if metric.disk_usage is not None else None,
        "network_in_bytes": metric.network_in_bytes,
        "network_out_bytes": metric.network_out_bytes,
        "load_1m": float(metric.load_1m) if metric.load_1m is not None else None,
        "load_5m": float(metric.load_5m) if metric.load_5m is not None else None,
        "load_15m": float(metric.load_15m) if metric.load_15m is not None else None,
        "tcp_connections": metric.tcp_connections,
        "uptime_seconds": metric.uptime_seconds,
    }


@router.get("/{server_id}/metrics/latest", summary="服务器最新指标")
def get_latest(
    server_id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询服务器最近一条监控指标。"""
    result = MonitorService(db).get_latest(server_id)
    return success(
        data={
            "server": ServerOut.model_validate(result["server"]).model_dump(),
            "metric": _metric_dict(result["metric"]),
        }
    )


@router.get("/{server_id}/metrics/history", summary="服务器历史指标（原始分页）")
def get_history(
    server_id: int,
    start: datetime = Query(..., description="起始时间"),
    end: datetime = Query(..., description="结束时间"),
    page_num: int = Query(1, ge=1, alias="page"),
    page_size: int = Query(100, ge=1, le=2000),
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询服务器原始历史指标。"""
    total, items = MonitorService(db).get_history(server_id, start, end, page_num, page_size)
    return success(data=page(total, [_metric_dict(m) for m in items]))


@router.get("/{server_id}/metrics/summary", summary="服务器指标聚合（图表）")
def get_summary(
    server_id: int,
    time_range: str = Query("1h", alias="range", pattern="^(1h|6h|24h|7d)$"),
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按时间范围分桶聚合指标，网络字段为差分速率（MB/s）。"""
    summary: MetricSummary = MonitorService(db).get_summary(server_id, time_range)
    return success(data=summary.model_dump(mode="json"))


@router.get("/{server_id}/assets", summary="服务器资产（磁盘/网卡）")
def get_assets(
    server_id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询服务器磁盘与网卡资产。"""
    result = MonitorService(db).get_assets(server_id)
    return success(
        data={
            "disks": [
                {"device_name": d.device_name, "mount_point": d.mount_point,
                 "filesystem": d.filesystem, "total_bytes": d.total_bytes}
                for d in result["disks"]
            ],
            "networks": [
                {"interface_name": n.interface_name, "mac_address": n.mac_address,
                 "ip_address": n.ip_address}
                for n in result["networks"]
            ],
        }
    )
