"""系统级信息采集：Load Average、TCP 连接数与运行时长。"""

from __future__ import annotations

import os
import platform
import socket
import time
from dataclasses import dataclass

import psutil


@dataclass
class SystemInfo:
    """系统级采集结果。"""

    load_1m: float
    load_5m: float
    load_15m: float
    tcp_connections: int
    uptime_seconds: int
    hostname: str
    kernel_version: str


def _read_tcp_connections() -> int:
    """统计 /proc/net/tcp 与 tcp6 的连接行数（Linux 专用）。"""
    total = 0
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                total += sum(1 for _ in f) - 1  # 去掉表头
        except OSError:
            pass
    return max(total, 0)


def collect() -> SystemInfo:
    """采集 Load、TCP 连接数、运行时长与主机信息。

    Returns:
        SystemInfo 对象。
    """
    load = os.getloadavg()
    return SystemInfo(
        load_1m=round(load[0], 2),
        load_5m=round(load[1], 2),
        load_15m=round(load[2], 2),
        tcp_connections=_read_tcp_connections(),
        uptime_seconds=int(time.time() - psutil.boot_time()),
        hostname=socket.gethostname(),
        kernel_version=platform.release(),
    )
