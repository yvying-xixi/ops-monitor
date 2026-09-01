"""Dashboard 汇总接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.schemas.server import ServerOut
from app.services.monitor_service import MonitorService
from app.utils.response import success

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _metric_summary(metric):
    if metric is None:
        return None
    return {
        "collected_at": metric.collected_at,
        "cpu_usage": float(metric.cpu_usage) if metric.cpu_usage is not None else None,
        "memory_usage": float(metric.memory_usage) if metric.memory_usage is not None else None,
        "disk_usage": float(metric.disk_usage) if metric.disk_usage is not None else None,
        "load_1m": float(metric.load_1m) if metric.load_1m is not None else None,
        "tcp_connections": metric.tcp_connections,
    }


@router.get("/overview", summary="Dashboard 汇总")
def get_overview(
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回服务器状态统计、平均使用率与服务器列表。"""
    result = MonitorService(db).get_overview()
    return success(
        data={
            "server_stats": result["server_stats"],
            "avg_usage": result["avg_usage"],
            "active_alerts": result["active_alerts"],
            "servers": [
                {
                    "server": ServerOut.model_validate(item["server"]).model_dump(),
                    "latest": _metric_summary(item["latest"]),
                }
                for item in result["servers"]
            ],
        }
    )
