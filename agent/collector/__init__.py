"""指标采集器聚合入口。"""

from __future__ import annotations

from . import cpu, disk, memory, network, system
from .cpu import CPUInfo
from .memory import MemoryInfo
from .network import NetworkInfo
from .system import SystemInfo


def collect_metrics() -> dict:
    """采集一轮指标，汇总为上报字典。

    Returns:
        含 cpu/memory/disk/network/load/tcp/uptime 的指标字典。
    """
    cpu_info: CPUInfo = cpu.collect()
    mem_info: MemoryInfo = memory.collect()
    net_info: NetworkInfo = network.collect_counts()
    sys_info: SystemInfo = system.collect()

    return {
        "cpu_usage": cpu_info.usage_percent,
        "memory_usage": mem_info.usage_percent,
        "memory_used_bytes": mem_info.used_bytes,
        "disk_usage": disk.collect_usage_percent(),
        "network_in_bytes": net_info.bytes_recv,
        "network_out_bytes": net_info.bytes_sent,
        "load_1m": sys_info.load_1m,
        "load_5m": sys_info.load_5m,
        "load_15m": sys_info.load_15m,
        "tcp_connections": sys_info.tcp_connections,
        "uptime_seconds": sys_info.uptime_seconds,
    }


def collect_system_info() -> dict:
    """采集注册所需的系统信息。

    Returns:
        含 hostname/os/cpu/memory/disk 的系统信息字典。
    """
    cpu_info = cpu.collect()
    mem_info = memory.collect()
    disk_total = sum(d.total_bytes or 0 for d in disk.collect_assets())
    sys_info = system.collect()
    return {
        "hostname": sys_info.hostname,
        "os_name": _os_name(),
        "os_version": _os_version(),
        "kernel_version": sys_info.kernel_version,
        "architecture": _architecture(),
        "cpu_model": cpu_info.model,
        "cpu_cores": cpu_info.cores,
        "memory_total_bytes": mem_info.total_bytes,
        "disk_total_bytes": disk_total,
    }


def collect_assets() -> dict:
    """采集磁盘与网卡资产列表。

    Returns:
        `{disks, networks}` 字典。
    """
    return {
        "disks": [a.__dict__ for a in disk.collect_assets()],
        "networks": [a.__dict__ for a in network.collect_assets()],
    }


def _os_name() -> str:
    import platform

    return platform.system()


def _os_version() -> str:
    import platform

    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.release()


def _architecture() -> str:
    import platform

    return platform.machine()
