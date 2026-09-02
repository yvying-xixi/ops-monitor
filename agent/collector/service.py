"""服务状态采集：通过 systemctl 查询服务运行状态。"""

from __future__ import annotations

import subprocess

ACTION_TIMEOUT = 10

STATUS_MAP = {"active": "RUNNING", "inactive": "STOPPED", "failed": "FAILED"}


def _is_active(service: str) -> str:
    """查询单个服务状态并映射为标准枚举。

    Returns:
        RUNNING/STOPPED/FAILED/UNKNOWN。
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=ACTION_TIMEOUT,
        )
        output = result.stdout.strip().lower()
        if result.returncode == 0:
            return "RUNNING"
        return STATUS_MAP.get(output, "UNKNOWN")
    except (subprocess.SubprocessError, OSError):
        return "UNKNOWN"


def collect_services(services: list[str]) -> list[dict]:
    """采集一批服务的状态。

    Args:
        services: 需要监控的服务名列表。

    Returns:
        `[{service_name, current_status}]` 列表。
    """
    return [
        {"service_name": name, "current_status": _is_active(name)}
        for name in services
    ]
