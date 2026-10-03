"""平台自有 Prometheus 指标。

指标值在抓取时从数据库汇总（多 worker 下仍一致），避免进程内计数器在多 worker
场景下的偏差。高基数标识（server_id / task_id / execution_id 等）不作为标签。
"""

from __future__ import annotations

from prometheus_client import Gauge, generate_latest
from sqlalchemy.orm import Session

AGENT_STATUSES = ("ONLINE", "WARNING", "OFFLINE", "UNKNOWN")
ALERT_SEVERITIES = ("WARNING", "CRITICAL")
TASK_STATUSES = (
    "CREATED",
    "PENDING",
    "RUNNING",
    "SUCCESS",
    "FAILED",
    "TIMEOUT",
    "CANCELLED",
    "RETRYING",
    "DEAD",
)

ops_agent_status = Gauge("ops_agent_status", "按 Agent 状态统计的服务器数量", ["status"])
ops_server_total = Gauge("ops_server_total", "启用中的服务器总数")
ops_alert_active = Gauge("ops_alert_active", "按严重级别统计的活动告警数量", ["severity"])
ops_task_status = Gauge("ops_task_status", "按状态统计的任务数量", ["status"])


def refresh_gauges(db: Session) -> None:
    """从数据库刷新所有指标值。"""
    from app.repositories import ServerRepository
    from app.repositories.alert_repository import AlertEventRepository
    from app.repositories.task_repository import TaskRepository

    server_counts = ServerRepository(db).get_status_counts()
    for status in AGENT_STATUSES:
        ops_agent_status.labels(status=status).set(server_counts.get(status, 0))
    ops_server_total.set(server_counts.get("total", 0))

    alert_counts = AlertEventRepository(db).count_active_by_severity()
    for severity in ALERT_SEVERITIES:
        ops_alert_active.labels(severity=severity).set(alert_counts.get(severity, 0))

    task_counts = TaskRepository(db).count_by_status()
    for status in TASK_STATUSES:
        ops_task_status.labels(status=status).set(task_counts.get(status, 0))


def render_latest() -> bytes:
    """返回 Prometheus 文本格式的指标快照。"""
    return generate_latest()
