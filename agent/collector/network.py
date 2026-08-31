"""网络信息采集：累计流量计数与网卡资产列表。"""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass
class NetworkInfo:
    """网络累计流量计数。"""

    bytes_sent: int
    bytes_recv: int


@dataclass
class NetworkAsset:
    """网卡资产。"""

    interface_name: str
    mac_address: str | None
    ip_address: str | None


def collect_counts() -> NetworkInfo:
    """采集全网络累计发送/接收字节数。

    Returns:
        NetworkInfo 对象。
    """
    counters = psutil.net_io_counters()
    return NetworkInfo(bytes_sent=counters.bytes_sent, bytes_recv=counters.bytes_recv)


def collect_assets() -> list[NetworkAsset]:
    """采集网卡资产列表（排除回环地址）。

    Returns:
        NetworkAsset 对象列表。
    """
    assets: list[NetworkAsset] = []
    for interface, addrs in psutil.net_if_addrs().items():
        if interface == "lo":
            continue
        mac = next((a.address for a in addrs if a.family == psutil.AF_LINK), None)
        ip = next((a.address for a in addrs if a.family == getattr(psutil, "AF_INET", None)), None)
        assets.append(
            NetworkAsset(interface_name=interface, mac_address=mac, ip_address=ip)
        )
    return assets
