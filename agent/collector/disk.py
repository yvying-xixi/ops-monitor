"""磁盘信息采集：整体使用率与磁盘资产列表。"""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass
class DiskAsset:
    """磁盘资产。"""

    device_name: str
    mount_point: str
    filesystem: str | None
    total_bytes: int | None


def collect_usage_percent() -> float:
    """采集根分区磁盘使用率。

    Returns:
        使用率百分比，采集失败返回 0。
    """
    try:
        return round(psutil.disk_usage("/").percent, 2)
    except OSError:
        return 0.0


def collect_assets() -> list[DiskAsset]:
    """采集磁盘资产列表（仅本机物理分区）。

    Returns:
        DiskAsset 对象列表。
    """
    assets: list[DiskAsset] = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except OSError:
            continue
        assets.append(
            DiskAsset(
                device_name=partition.device,
                mount_point=partition.mountpoint,
                filesystem=partition.fstype,
                total_bytes=usage.total,
            )
        )
    return assets
