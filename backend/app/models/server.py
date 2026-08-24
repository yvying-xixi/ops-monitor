from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.mysql import BIGINT, CHAR, INTEGER, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OpsServer(Base):
    __tablename__ = "ops_server"
    __table_args__ = {"comment": "服务器资产表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="服务器ID")
    server_code: Mapped[str] = mapped_column(String(64), unique=True, comment="服务器唯一编码")
    hostname: Mapped[str] = mapped_column(String(128), comment="主机名")
    ip_address: Mapped[str] = mapped_column(String(64), comment="服务器IP地址")
    ssh_port: Mapped[int] = mapped_column(SMALLINT(unsigned=True), default=22, comment="SSH端口")
    os_name: Mapped[str | None] = mapped_column(String(128), comment="操作系统名称")
    os_version: Mapped[str | None] = mapped_column(String(128), comment="操作系统版本")
    kernel_version: Mapped[str | None] = mapped_column(String(128), comment="内核版本")
    architecture: Mapped[str | None] = mapped_column(String(32), comment="系统架构")
    cpu_model: Mapped[str | None] = mapped_column(String(255), comment="CPU型号")
    cpu_cores: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), comment="CPU逻辑核心数")
    memory_total_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="内存总量，单位：字节")
    disk_total_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="磁盘总量，单位：字节")
    agent_version: Mapped[str | None] = mapped_column(String(32), comment="Agent版本")
    agent_status: Mapped[str] = mapped_column(String(16), default="OFFLINE", comment="Agent状态")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最后心跳时间")
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, comment="Agent注册时间")
    status: Mapped[int] = mapped_column(SMALLINT, default=1, comment="资产状态：0停用，1启用")
    remark: Mapped[str | None] = mapped_column(String(500), comment="备注")
    created_by: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("sys_user.id"), comment="创建人"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, comment="软删除时间")

    creator: Mapped[SysUser | None] = relationship("SysUser", foreign_keys=[created_by])
    disks: Mapped[list[OpsServerDisk]] = relationship("OpsServerDisk", back_populates="server")
    networks: Mapped[list[OpsServerNetwork]] = relationship("OpsServerNetwork", back_populates="server")
    services: Mapped[list[OpsServerService]] = relationship("OpsServerService", back_populates="server")
    containers: Mapped[list[OpsServerContainer]] = relationship("OpsServerContainer", back_populates="server")
    agent_tokens: Mapped[list[OpsAgentToken]] = relationship("OpsAgentToken", back_populates="server")
    heartbeats: Mapped[list[OpsAgentHeartbeat]] = relationship("OpsAgentHeartbeat", back_populates="server")
    metrics: Mapped[list[MonitorServerMetric]] = relationship("MonitorServerMetric", back_populates="server")


class OpsServerDisk(Base):
    __tablename__ = "ops_server_disk"
    __table_args__ = {"comment": "服务器磁盘资产表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="磁盘资产ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    device_name: Mapped[str] = mapped_column(String(128), comment="设备名称")
    mount_point: Mapped[str | None] = mapped_column(String(255), comment="挂载点")
    filesystem: Mapped[str | None] = mapped_column(String(64), comment="文件系统")
    total_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="磁盘总量，单位：字节")
    status: Mapped[int] = mapped_column(SMALLINT, default=1, comment="状态：0停用，1启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    server: Mapped[OpsServer] = relationship("OpsServer", back_populates="disks")


class OpsServerNetwork(Base):
    __tablename__ = "ops_server_network"
    __table_args__ = {"comment": "服务器网卡资产表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="网卡资产ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    interface_name: Mapped[str] = mapped_column(String(128), comment="网卡名称")
    mac_address: Mapped[str | None] = mapped_column(String(64), comment="MAC地址")
    ip_address: Mapped[str | None] = mapped_column(String(64), comment="网卡IP地址")
    status: Mapped[int] = mapped_column(SMALLINT, default=1, comment="状态：0停用，1启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    server: Mapped[OpsServer] = relationship("OpsServer", back_populates="networks")


class OpsAgentToken(Base):
    __tablename__ = "ops_agent_token"
    __table_args__ = {"comment": "Agent鉴权Token表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="Token记录ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    token_name: Mapped[str] = mapped_column(String(64), comment="Token名称")
    token_prefix: Mapped[str] = mapped_column(String(16), comment="Token前缀，用于识别")
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, comment="Token哈希，不保存明文")
    status: Mapped[int] = mapped_column(SMALLINT, default=1, comment="状态：0撤销，1有效")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, comment="过期时间")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最后使用时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, comment="撤销时间")

    server: Mapped[OpsServer] = relationship("OpsServer", back_populates="agent_tokens")


class OpsAgentHeartbeat(Base):
    __tablename__ = "ops_agent_heartbeat"
    __table_args__ = {"comment": "Agent心跳历史表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="心跳记录ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    agent_version: Mapped[str | None] = mapped_column(String(32), comment="Agent版本")
    ip_address: Mapped[str | None] = mapped_column(String(64), comment="Agent上报IP")
    collected_at: Mapped[datetime] = mapped_column(DateTime, comment="心跳时间")
    received_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="服务端接收时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    server: Mapped[OpsServer] = relationship("OpsServer", back_populates="heartbeats")


class OpsServerService(Base):
    __tablename__ = "ops_server_service"
    __table_args__ = {"comment": "服务器服务资产表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="服务资产ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    service_name: Mapped[str] = mapped_column(String(64), comment="systemd服务名称")
    display_name: Mapped[str | None] = mapped_column(String(128), comment="展示名称")
    service_type: Mapped[str] = mapped_column(String(32), default="SYSTEMD", comment="SYSTEMD/DOCKER/CUSTOM")
    is_whitelisted: Mapped[int] = mapped_column(SMALLINT, default=1, comment="是否允许执行受控操作")
    is_critical: Mapped[int] = mapped_column(SMALLINT, default=0, comment="是否为关键服务")
    current_status: Mapped[str | None] = mapped_column(String(32), comment="RUNNING/STOPPED/FAILED/UNKNOWN")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最后检查时间")
    status: Mapped[int] = mapped_column(SMALLINT, default=1, comment="状态：0停用，1启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    server: Mapped[OpsServer] = relationship("OpsServer", back_populates="services")


class OpsServerContainer(Base):
    __tablename__ = "ops_server_container"
    __table_args__ = {"comment": "Docker容器资产表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="容器资产ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    container_id: Mapped[str] = mapped_column(String(128), comment="容器ID")
    container_name: Mapped[str] = mapped_column(String(255), comment="容器名称")
    image_name: Mapped[str | None] = mapped_column(String(255), comment="镜像名称")
    container_status: Mapped[str | None] = mapped_column(String(32), comment="RUNNING/STOPPED/PAUSED/EXITED")
    restart_count: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), comment="重启次数")
    container_created_at: Mapped[datetime | None] = mapped_column(DateTime, comment="容器创建时间")
    is_critical: Mapped[int] = mapped_column(SMALLINT, default=0, comment="是否为关键容器")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, comment="最后发现时间")
    status: Mapped[int] = mapped_column(SMALLINT, default=1, comment="状态：0停用，1启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    server: Mapped[OpsServer] = relationship("OpsServer", back_populates="containers")
