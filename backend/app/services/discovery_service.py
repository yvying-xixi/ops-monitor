"""只读服务器发现：在白名单 CIDR 内做端口 / SSH banner 探测。

安全边界（见 ADR-012）：
- 默认关闭，`DISCOVERY_ENABLED` 控制；
- 目标 CIDR 必须是 `DISCOVERY_ALLOWED_CIDRS` 白名单的子网，防止 SSRF / 越权扫描；
- **不持有任何凭据、不进行认证、不远程安装**，仅 TCP 连接与 banner 读取。
"""

from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.exceptions import AppException, ErrorCode


def _parse_networks(cidrs: list[str]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks = []
    for cidr in cidrs:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            continue
    return networks


def _is_within_allowed(
    target: ipaddress.IPv4Network | ipaddress.IPv6Network,
    allowed: list[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    for network in allowed:
        try:
            if target.subnet_of(network):  # type: ignore[arg-type]
                return True
        except TypeError:  # 版本不一致（IPv4 vs IPv6）
            continue
    return False


def _probe(ip: str, port: int, timeout: float) -> tuple[bool, str | None]:
    """对单个 IP 做 TCP 连接并尝试读取 banner（不认证）。"""
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            if sock.connect_ex((ip, port)) != 0:
                return False, None
            try:
                sock.settimeout(timeout)
                banner = sock.recv(256).decode("utf-8", errors="replace").strip()
            except OSError:
                banner = ""
            return True, (banner or None)
    except OSError:
        return False, None


def allowed_cidrs() -> list[str]:
    """返回配置的允许扫描网段（去重、去空）。"""
    return sorted({c for c in settings.DISCOVERY_ALLOWED_CIDRS if c.strip()})


def scan(cidr: str, port: int | None = None) -> list[dict]:
    """在白名单内扫描 CIDR，返回开放端口的主机列表。

    Raises:
        AppException: 功能未启用（403）、CIDR 非法或超出白名单（403）、主机数超上限（400）。
    """
    if not settings.DISCOVERY_ENABLED:
        raise AppException(ErrorCode.FORBIDDEN, "服务器发现功能未启用", http_status=403)

    allowed = _parse_networks(settings.DISCOVERY_ALLOWED_CIDRS)
    if not allowed:
        raise AppException(ErrorCode.FORBIDDEN, "未配置允许扫描的 CIDR 白名单", http_status=403)

    try:
        target = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        raise AppException(ErrorCode.BAD_REQUEST, "CIDR 格式非法", http_status=400) from None

    if not _is_within_allowed(target, allowed):
        raise AppException(
            ErrorCode.FORBIDDEN, "目标网段超出允许扫描的白名单范围", http_status=403
        )

    hosts = list(target.hosts())
    if len(hosts) > settings.DISCOVERY_MAX_HOSTS:
        raise AppException(
            ErrorCode.BAD_REQUEST,
            f"主机数 {len(hosts)} 超过上限 {settings.DISCOVERY_MAX_HOSTS}，请缩小网段",
            http_status=400,
        )

    scan_port = port or settings.DISCOVERY_SSH_PORT
    if len(hosts) == 0:
        return []

    workers = max(1, min(settings.DISCOVERY_CONCURRENCY, len(hosts)))
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for host, (is_open, banner) in zip(
            hosts,
            pool.map(lambda h: _probe(str(h), scan_port, settings.DISCOVERY_TIMEOUT_SECONDS), hosts),
            strict=True,
        ):
            if is_open:
                results.append({"ip": str(host), "port": scan_port, "banner": banner})

    results.sort(key=lambda item: ipaddress.ip_address(item["ip"]))
    return results
