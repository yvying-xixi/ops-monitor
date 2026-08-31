"""CPU 信息采集。"""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass
class CPUInfo:
    """CPU 采集结果。"""

    usage_percent: float
    cores: int
    model: str | None


def _read_cpu_model() -> str | None:
    """从 /proc/cpuinfo 读取 CPU 型号。"""
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def collect() -> CPUInfo:
    """采集 CPU 使用率、逻辑核心数与型号。

    Returns:
        CPUInfo 对象。
    """
    usage = psutil.cpu_percent(interval=0.5)
    return CPUInfo(
        usage_percent=round(usage, 2),
        cores=psutil.cpu_count(logical=True) or 0,
        model=_read_cpu_model(),
    )
