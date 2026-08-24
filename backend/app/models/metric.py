from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MonitorServerMetric(Base):
    __tablename__ = "monitor_server_metric"
    __table_args__ = {"comment": "服务器监控指标表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="指标记录ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, comment="采集时间")
    cpu_usage: Mapped[float | None] = mapped_column(Numeric(5, 2), comment="CPU使用率，百分比")
    memory_usage: Mapped[float | None] = mapped_column(Numeric(5, 2), comment="内存使用率，百分比")
    memory_used_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="已使用内存，单位：字节")
    disk_usage: Mapped[float | None] = mapped_column(Numeric(5, 2), comment="整体磁盘使用率，百分比")
    network_in_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计入站字节数")
    network_out_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计出站字节数")
    load_1m: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="1分钟Load")
    load_5m: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="5分钟Load")
    load_15m: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="15分钟Load")
    tcp_connections: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), comment="TCP连接数")
    uptime_seconds: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="系统运行时长，单位：秒")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    server: Mapped[OpsServer] = relationship("OpsServer", back_populates="metrics")


class MonitorDiskMetric(Base):
    __tablename__ = "monitor_disk_metric"
    __table_args__ = {"comment": "磁盘监控指标表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="磁盘指标记录ID")
    disk_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server_disk.id"), comment="磁盘资产ID"
    )
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, comment="采集时间")
    used_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="已使用容量，单位：字节")
    total_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="总容量，单位：字节")
    usage_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), comment="使用率，百分比")
    read_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计读取字节数")
    write_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计写入字节数")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    disk: Mapped[OpsServerDisk] = relationship("OpsServerDisk")
    server: Mapped[OpsServer] = relationship("OpsServer")


class MonitorNetworkMetric(Base):
    __tablename__ = "monitor_network_metric"
    __table_args__ = {"comment": "网卡监控指标表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="网卡指标记录ID")
    network_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server_network.id"), comment="网卡资产ID"
    )
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, comment="采集时间")
    bytes_received: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计接收字节数")
    bytes_sent: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计发送字节数")
    packets_received: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计接收数据包数")
    packets_sent: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计发送数据包数")
    errors_received: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), comment="接收错误数")
    errors_sent: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), comment="发送错误数")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    network: Mapped[OpsServerNetwork] = relationship("OpsServerNetwork")
    server: Mapped[OpsServer] = relationship("OpsServer")


class MonitorContainerMetric(Base):
    __tablename__ = "monitor_container_metric"
    __table_args__ = {"comment": "Docker容器监控指标表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="容器指标记录ID")
    container_asset_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server_container.id"), comment="容器资产ID"
    )
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    container_id: Mapped[str] = mapped_column(String(128), comment="容器ID快照")
    container_status: Mapped[str | None] = mapped_column(String(32), comment="RUNNING/STOPPED/PAUSED/EXITED")
    cpu_usage: Mapped[float | None] = mapped_column(Numeric(7, 3), comment="CPU使用率")
    memory_usage: Mapped[float | None] = mapped_column(Numeric(7, 3), comment="内存使用率")
    memory_used_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="容器已使用内存")
    network_in_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计入站字节数")
    network_out_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="累计出站字节数")
    restart_count: Mapped[int | None] = mapped_column(INTEGER(unsigned=True), comment="重启次数")
    collected_at: Mapped[datetime] = mapped_column(DateTime, comment="采集时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    container_asset: Mapped[OpsServerContainer] = relationship("OpsServerContainer")
    server: Mapped[OpsServer] = relationship("OpsServer")


class MonitorProcessSnapshot(Base):
    __tablename__ = "monitor_process_snapshot"
    __table_args__ = {"comment": "服务器进程快照表"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="进程快照记录ID")
    server_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("ops_server.id"), comment="服务器ID"
    )
    process_pid: Mapped[int] = mapped_column(INTEGER(unsigned=True), comment="进程PID")
    process_name: Mapped[str | None] = mapped_column(String(255), comment="进程名称")
    username: Mapped[str | None] = mapped_column(String(128), comment="进程所属用户")
    cpu_percent: Mapped[float | None] = mapped_column(Numeric(7, 3), comment="进程CPU使用率")
    memory_percent: Mapped[float | None] = mapped_column(Numeric(7, 3), comment="进程内存使用率")
    memory_bytes: Mapped[int | None] = mapped_column(BIGINT(unsigned=True), comment="进程内存占用")
    process_status: Mapped[str | None] = mapped_column(String(32), comment="进程状态")
    command_line: Mapped[str | None] = mapped_column(Text, comment="命令行，注意脱敏")
    collected_at: Mapped[datetime] = mapped_column(DateTime, comment="采集时间")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间"
    )

    server: Mapped[OpsServer] = relationship("OpsServer")
