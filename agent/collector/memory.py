"""内存信息采集。"""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass
class MemoryInfo:
    """内存采集结果。"""

    total_bytes: int
    used_bytes: int
    usage_percent: float


def collect() -> MemoryInfo:
    """采集内存总量、已使用量与使用率。

    Returns:
        MemoryInfo 对象。
    """
    vm = psutil.virtual_memory()
    return MemoryInfo(
        total_bytes=vm.total,
        used_bytes=vm.used,
        usage_percent=round(vm.percent, 2),
    )
