"""监控中心服务：指标查询、聚合差分与 Dashboard 汇总。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.exceptions import AppException, ErrorCode
from app.models import MonitorServerMetric, OpsServer
from app.repositories import (
    AlertEventRepository,
    MetricRepository,
    NetworkRepository,
    ServerRepository,
)
from app.repositories.server_repository import DiskRepository
from app.schemas.monitor import MetricSummary

RANGE_CONFIG = {
    "1h": {"seconds": 3600, "bucket": 60},
    "6h": {"seconds": 21600, "bucket": 60},
    "24h": {"seconds": 86400, "bucket": 300},
    "7d": {"seconds": 604800, "bucket": 3600},
}

_MB = 1024 * 1024


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MonitorService:
    """监控数据查询业务逻辑。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.server_repo = ServerRepository(db)
        self.metric_repo = MetricRepository(db)
        self.disk_repo = DiskRepository(db)
        self.network_repo = NetworkRepository(db)

    def _get_server(self, server_id: int) -> OpsServer:
        server = self.server_repo.get(server_id)
        if server is None:
            raise AppException(ErrorCode.SERVER_NOT_FOUND, "服务器不存在", http_status=404)
        return server

    def get_latest(self, server_id: int) -> dict:
        """查询服务器最新指标。"""
        server = self._get_server(server_id)
        metric = self.metric_repo.get_latest(server_id)
        return {"server": server, "metric": metric}

    def get_history(
        self,
        server_id: int,
        start: datetime,
        end: datetime,
        page: int,
        page_size: int,
    ) -> tuple[int, list[MonitorServerMetric]]:
        """分页查询原始历史指标。"""
        self._get_server(server_id)
        return self.metric_repo.get_history(server_id, start, end, page=page, page_size=page_size)

    def get_summary(self, server_id: int, range_key: str) -> MetricSummary:
        """按时间范围分桶聚合，网络字段输出差分速率（MB/s）。"""
        server = self._get_server(server_id)
        if range_key not in RANGE_CONFIG:
            raise AppException(ErrorCode.BAD_REQUEST, "不支持的 time range", http_status=400)

        cfg = RANGE_CONFIG[range_key]
        end = _utcnow()
        start = end - timedelta(seconds=cfg["seconds"])
        rows = self.metric_repo.get_summary(server.id, start, end, cfg["bucket"])

        points = []
        prev_in = prev_out = None
        for row in rows:
            network_in_rate = 0.0
            network_out_rate = 0.0
            if prev_in is not None and row.network_in_max is not None:
                network_in_rate = round(max(0, row.network_in_max - prev_in) / cfg["bucket"] / _MB, 4)
            if prev_out is not None and row.network_out_max is not None:
                network_out_rate = round(max(0, row.network_out_max - prev_out) / cfg["bucket"] / _MB, 4)
            prev_in = row.network_in_max
            prev_out = row.network_out_max

            point = {
                "time": row.bucket,
                "cpu_usage": self._bucket(row.cpu_usage_avg, row.cpu_usage_max, row.cpu_usage_min),
                "memory_usage": self._bucket(row.memory_usage_avg, row.memory_usage_max, row.memory_usage_min),
                "disk_usage": self._bucket(row.disk_usage_avg, row.disk_usage_max, row.disk_usage_min),
                "load_1m": self._bucket(row.load_1m_avg, row.load_1m_max, row.load_1m_min),
                "load_5m": self._bucket(row.load_5m_avg, row.load_5m_max, row.load_5m_min),
                "load_15m": self._bucket(row.load_15m_avg, row.load_15m_max, row.load_15m_min),
                "tcp_connections": self._bucket(row.tcp_connections_avg, row.tcp_connections_max, row.tcp_connections_min),
                "network_in_rate": network_in_rate,
                "network_out_rate": network_out_rate,
            }
            points.append(point)

        return MetricSummary(
            range=range_key,
            bucket_seconds=cfg["bucket"],
            start=start,
            end=end,
            points=points,
        )

    @staticmethod
    def _bucket(avg, max_, min_) -> dict | None:
        """构造聚合值字典，全空时返回 None。"""
        if avg is None and max_ is None and min_ is None:
            return None
        return {
            "avg": round(float(avg), 2) if avg is not None else None,
            "max": round(float(max_), 2) if max_ is not None else None,
            "min": round(float(min_), 2) if min_ is not None else None,
        }

    def get_assets(self, server_id: int) -> dict:
        """查询服务器磁盘与网卡资产。"""
        server = self._get_server(server_id)
        disks = self.disk_repo.list_all(server_id=server.id, status=1)
        networks = self.network_repo.list_all(server_id=server.id, status=1)
        return {"disks": disks, "networks": networks}

    def get_overview(self) -> dict:
        """Dashboard 汇总：服务器状态统计、平均使用率、实时告警与服务器列表。"""
        server_stats = self.server_repo.get_status_counts()
        cpu, memory, disk = self.metric_repo.get_server_usage_avg()
        active_alerts = AlertEventRepository(self.db).count_active()
        servers = self.server_repo.list_active()
        latest_map = self.metric_repo.get_latest_map([s.id for s in servers])

        server_list = []
        for server in servers:
            metric = latest_map.get(server.id)
            server_list.append(
                {
                    "server": server,
                    "latest": metric,
                }
            )
        server_list.sort(key=lambda item: item["server"].id, reverse=True)

        return {
            "server_stats": server_stats,
            "avg_usage": {"cpu": cpu, "memory": memory, "disk": disk},
            "active_alerts": active_alerts,
            "servers": server_list,
        }
