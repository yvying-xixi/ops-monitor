"""Agent 协议服务：注册、心跳、指标入库与资产同步。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.exceptions import AppException, ErrorCode
from app.models import OpsServer, MonitorServerMetric
from app.repositories import (
    AgentTokenRepository,
    HeartbeatRepository,
    MetricRepository,
    ServerRepository,
)
from app.repositories.server_repository import DiskRepository, NetworkRepository
from app.schemas.agent import AssetsRequest, HeartbeatRequest, MetricsRequest, RegisterRequest

MAX_TIME_SKEW_SECONDS = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgentService:
    """Agent 协议业务逻辑，事务提交统一在此层完成。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.server_repo = ServerRepository(db)
        self.token_repo = AgentTokenRepository(db)
        self.heartbeat_repo = HeartbeatRepository(db)
        self.metric_repo = MetricRepository(db)
        self.disk_repo = DiskRepository(db)
        self.network_repo = NetworkRepository(db)

    def register(self, data: RegisterRequest, *, ip: str | None = None) -> dict:
        """Agent 注册：校验凭证并回写系统信息。

        Args:
            data: 注册请求体。
            ip: Agent 上报 IP。

        Returns:
            `{server_id, agent_status}`。

        Raises:
            AppException: Token 无效（40103）、服务器不存在（40403）、编码不匹配（40103）。
        """
        token = self.token_repo.authenticate(data.token)
        if token is None:
            raise AppException(ErrorCode.AGENT_UNAUTHORIZED, "Agent 凭证无效", http_status=401)

        server = self.server_repo.get(token.server_id)
        if server is None or server.status != 1:
            raise AppException(ErrorCode.SERVER_NOT_FOUND, "服务器不存在或已停用", http_status=404)
        if server.server_code != data.server_code:
            raise AppException(
                ErrorCode.AGENT_UNAUTHORIZED, "服务器编码与凭证不匹配", http_status=401
            )

        fields = data.model_dump(exclude={"server_code", "token"})
        self.server_repo.register_server(server, fields)
        if ip:
            server.ip_address = ip
        self.heartbeat_repo.record(server_id=server.id, agent_version=data.agent_version, ip_address=ip)
        self.token_repo.update_last_used(token)
        self.db.commit()
        return {"server_id": server.id, "agent_status": "ONLINE"}

    def heartbeat(
        self,
        server: OpsServer,
        data: HeartbeatRequest,
        *,
        ip: str | None = None,
    ) -> dict:
        """处理心跳：更新服务器状态并记录心跳历史。

        Args:
            server: 由 Token 解析出的服务器。
            data: 心跳请求体。
            ip: Agent 上报 IP。

        Returns:
            `{server_id, received_at}`。
        """
        self._assert_server_match(server, data.server_id)
        self.server_repo.update_last_heartbeat(server, ip=ip, agent_version=data.agent_version)
        self.heartbeat_repo.record(
            server_id=server.id,
            agent_version=data.agent_version,
            ip_address=ip,
            collected_at=self._normalize_utc(data.timestamp) if data.timestamp else _utcnow(),
        )
        self.db.commit()
        return {"server_id": server.id, "received_at": _utcnow().isoformat()}

    def ingest_metrics(self, server: OpsServer, data: MetricsRequest) -> dict:
        """处理指标上报：校验时间合法性并落库。

        Args:
            server: 由 Token 解析出的服务器。
            data: 指标请求体。

        Returns:
            `{server_id, recorded_at}`。

        Raises:
            AppException: 采集时间与服务器时间偏差过大（40001）。
        """
        self._assert_server_match(server, data.server_id)
        collected_at = self._validate_timestamp(data.timestamp)

        metric = MonitorServerMetric(
            server_id=server.id,
            collected_at=collected_at,
            cpu_usage=data.cpu_usage,
            memory_usage=data.memory_usage,
            memory_used_bytes=data.memory_used_bytes,
            disk_usage=data.disk_usage,
            network_in_bytes=data.network_in_bytes,
            network_out_bytes=data.network_out_bytes,
            load_1m=data.load_1m,
            load_5m=data.load_5m,
            load_15m=data.load_15m,
            tcp_connections=data.tcp_connections,
            uptime_seconds=data.uptime_seconds,
        )
        self.metric_repo.record(metric)
        self.db.commit()
        return {"server_id": server.id, "recorded_at": _utcnow().isoformat()}

    def sync_assets(self, server: OpsServer, data: AssetsRequest) -> dict:
        """同步磁盘与网卡资产（幂等 upsert，删除缺失项）。"""
        self._assert_server_match(server, data.server_id)

        disk_keys = set()
        for disk in data.disks:
            self.disk_repo.upsert(
                server.id,
                device_name=disk.device_name,
                mount_point=disk.mount_point,
                filesystem=disk.filesystem,
                total_bytes=disk.total_bytes,
            )
            disk_keys.add((disk.device_name, disk.mount_point))
        self.disk_repo.delete_missing(server.id, disk_keys)

        network_keys = {net.interface_name for net in data.networks}
        for net in data.networks:
            self.network_repo.upsert(
                server.id,
                interface_name=net.interface_name,
                mac_address=net.mac_address,
                ip_address=net.ip_address,
            )
        for network in self.network_repo.list_all(server_id=server.id):
            if network.interface_name not in network_keys:
                self.network_repo.delete(network)

        self.db.commit()
        return {"server_id": server.id, "synced_at": _utcnow().isoformat()}

    def _assert_server_match(self, server: OpsServer, server_id: int | None) -> None:
        """交叉校验请求体中的 server_id 与 Token 绑定服务器一致。"""
        if server_id is not None and server_id != server.id:
            raise AppException(
                ErrorCode.AGENT_UNAUTHORIZED, "服务器 ID 与凭证不匹配", http_status=401
            )

    @staticmethod
    def _normalize_utc(dt: datetime) -> datetime:
        """将任意时区的时间归一化为 naive UTC，用于落库与比较。"""
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def _validate_timestamp(self, collected_at: datetime) -> None:
        """校验采集时间与服务器时间偏差不超过允许范围。"""
        now = _utcnow()
        normalized = self._normalize_utc(collected_at)
        if abs((now - normalized).total_seconds()) > MAX_TIME_SKEW_SECONDS:
            raise AppException(ErrorCode.INVALID_TIMESTAMP, "采集时间非法", http_status=400)
        return normalized
