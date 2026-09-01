"""服务器资产与 Agent 相关仓储。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select, update

from app.models import (
    OpsAgentHeartbeat,
    OpsAgentToken,
    OpsServer,
    OpsServerDisk,
    OpsServerNetwork,
)
from app.repositories.base import BaseRepository

_UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(_UTC).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    """对 Token 明文进行 SHA-256 哈希，用于数据库存储与比对。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ServerRepository(BaseRepository[OpsServer]):
    """服务器资产仓储。"""

    model = OpsServer

    def get_by_server_code(self, server_code: str) -> OpsServer | None:
        return self.get_by(server_code=server_code)

    def get_by_ip_port(self, ip_address: str, ssh_port: int) -> OpsServer | None:
        return self.get_by(ip_address=ip_address, ssh_port=ssh_port)

    def register_server(self, server: OpsServer, data: dict) -> OpsServer:
        """Agent 注册时回写系统信息并置为在线。

        Args:
            server: 目标服务器资产。
            data: 注册请求中的系统信息字段映射。

        Returns:
            更新后的服务器对象。
        """
        for field in (
            "hostname",
            "os_name",
            "os_version",
            "kernel_version",
            "architecture",
            "cpu_model",
            "cpu_cores",
            "memory_total_bytes",
            "disk_total_bytes",
            "agent_version",
        ):
            if field in data and data[field] is not None:
                setattr(server, field, data[field])
        server.registered_at = _utcnow()
        server.last_heartbeat_at = _utcnow()
        server.agent_status = "ONLINE"
        self.db.flush()
        return server

    def update_last_heartbeat(
        self,
        server: OpsServer,
        *,
        ip: str | None = None,
        agent_version: str | None = None,
    ) -> OpsServer:
        """更新服务器最后心跳时间。

        Args:
            server: 目标服务器对象。
            ip: Agent 上报 IP。
            agent_version: Agent 版本。

        Returns:
            更新后的服务器对象。
        """
        server.last_heartbeat_at = _utcnow()
        if ip:
            server.ip_address = ip
        if agent_version:
            server.agent_version = agent_version
        server.agent_status = "ONLINE"
        self.db.flush()
        return server

    def refresh_agent_statuses(self) -> int:
        """按最后心跳时间批量刷新 Agent 状态。

        ≤30s ONLINE；30~90s WARNING；>90s OFFLINE。

        Returns:
            受影响的行数。
        """
        now = datetime.now(_UTC).replace(tzinfo=None)
        stmt = (
            update(OpsServer)
            .where(OpsServer.status == 1, OpsServer.deleted_at.is_(None))
            .values(
                agent_status=case(
                    (OpsServer.last_heartbeat_at >= now - timedelta(seconds=30), "ONLINE"),
                    (OpsServer.last_heartbeat_at >= now - timedelta(seconds=90), "WARNING"),
                    else_="OFFLINE",
                )
            )
        )
        result = self.db.execute(stmt)
        return result.rowcount or 0

    def get_status_counts(self) -> dict:
        """统计各 Agent 状态的服务器数量。

        Returns:
            `{ONLINE, WARNING, OFFLINE, UNKNOWN, total}` 计数。
        """
        stmt = (
            select(OpsServer.agent_status, func.count())
            .where(OpsServer.status == 1, OpsServer.deleted_at.is_(None))
            .group_by(OpsServer.agent_status)
        )
        counts = {"ONLINE": 0, "WARNING": 0, "OFFLINE": 0, "UNKNOWN": 0}
        for status, count in self.db.execute(stmt):
            counts[status] = count
        counts["total"] = sum(counts.values())
        return counts

    def list_active(self) -> list[OpsServer]:
        """查询全部启用且未删除的服务器。"""
        return self.list_all(status=1)


class AgentTokenRepository(BaseRepository[OpsAgentToken]):
    """Agent 鉴权 Token 仓储。"""

    model = OpsAgentToken

    def create_token(self, server_id: int, token_name: str | None = None) -> tuple[OpsAgentToken, str]:
        """生成高熵 Agent Token，仅返回一次明文，数据库只存 SHA-256 哈希。

        Args:
            server_id: 服务器 ID。
            token_name: Token 名称。

        Returns:
            (Token 记录对象, Token 明文)。
        """
        plaintext = secrets.token_urlsafe(32)
        token = OpsAgentToken(
            server_id=server_id,
            token_name=token_name or "default",
            token_prefix=plaintext[:8],
            token_hash=_hash_token(plaintext),
            status=1,
        )
        self.create(token)
        return token, plaintext

    def get_by_token_hash(self, token_hash: str) -> OpsAgentToken | None:
        return self.get_by(token_hash=token_hash)

    def authenticate(self, plaintext: str) -> OpsAgentToken | None:
        """按明文 Token 校验有效状态并返回记录。

        Args:
            plaintext: Token 明文。

        Returns:
            有效且未过期/未撤销的 Token 记录；否则返回 None。
        """
        token = self.get_by_token_hash(_hash_token(plaintext))
        if token is None or token.status != 1:
            return None
        if token.expires_at is not None and token.expires_at < _utcnow():
            return None
        if token.revoked_at is not None:
            return None
        return token

    def revoke(self, token: OpsAgentToken) -> OpsAgentToken:
        token.status = 0
        token.revoked_at = _utcnow()
        self.db.flush()
        return token

    def update_last_used(self, token: OpsAgentToken) -> None:
        token.last_used_at = _utcnow()
        self.db.flush()


class HeartbeatRepository(BaseRepository[OpsAgentHeartbeat]):
    """Agent 心跳历史仓储。"""

    model = OpsAgentHeartbeat

    def record(
        self,
        *,
        server_id: int,
        agent_version: str | None = None,
        ip_address: str | None = None,
        collected_at: datetime | None = None,
    ) -> OpsAgentHeartbeat:
        return self.create(
            OpsAgentHeartbeat(
                server_id=server_id,
                agent_version=agent_version,
                ip_address=ip_address,
                collected_at=collected_at or _utcnow(),
            )
        )


class DiskRepository(BaseRepository[OpsServerDisk]):
    """磁盘资产仓储。"""

    model = OpsServerDisk

    def upsert(self, server_id: int, *, device_name: str, mount_point: str | None, filesystem: str | None, total_bytes: int | None) -> OpsServerDisk:
        """按 (server_id, device_name, mount_point) 幂等写入磁盘资产。"""
        existing = self.db.scalars(
            select(OpsServerDisk).where(
                OpsServerDisk.server_id == server_id,
                OpsServerDisk.device_name == device_name,
                OpsServerDisk.mount_point == mount_point,
            )
        ).first()
        if existing:
            existing.filesystem = filesystem or existing.filesystem
            existing.total_bytes = total_bytes if total_bytes is not None else existing.total_bytes
            self.db.flush()
            return existing
        return self.create(
            OpsServerDisk(
                server_id=server_id,
                device_name=device_name,
                mount_point=mount_point,
                filesystem=filesystem,
                total_bytes=total_bytes,
            )
        )

    def delete_missing(self, server_id: int, present_keys: list[tuple]) -> None:
        """删除未出现在上报列表中的磁盘资产（按 server_id+device+mount 判定）。"""
        for disk in self.list_all(server_id=server_id):
            key = (disk.device_name, disk.mount_point)
            if key not in present_keys:
                self.delete(disk)


class NetworkRepository(BaseRepository[OpsServerNetwork]):
    """网卡资产仓储。"""

    model = OpsServerNetwork

    def upsert(self, server_id: int, *, interface_name: str, mac_address: str | None, ip_address: str | None) -> OpsServerNetwork:
        """按 (server_id, interface_name) 幂等写入网卡资产。"""
        existing = self.db.scalars(
            select(OpsServerNetwork).where(
                OpsServerNetwork.server_id == server_id,
                OpsServerNetwork.interface_name == interface_name,
            )
        ).first()
        if existing:
            existing.mac_address = mac_address or existing.mac_address
            existing.ip_address = ip_address or existing.ip_address
            self.db.flush()
            return existing
        return self.create(
            OpsServerNetwork(
                server_id=server_id,
                interface_name=interface_name,
                mac_address=mac_address,
                ip_address=ip_address,
            )
        )
