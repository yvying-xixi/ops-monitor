"""注册、心跳与指标上报封装。"""

from __future__ import annotations

from datetime import datetime, timezone

from .client import AgentClient


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def register(client: AgentClient, *, server_code: str, token: str, system_info: dict, agent_version: str) -> dict:
    """向服务端注册 Agent。

    Args:
        client: 上报客户端。
        server_code: 服务器唯一编码。
        token: Agent Token（注册协议要求在请求体内携带）。
        system_info: 系统信息字典。
        agent_version: Agent 版本。

    Returns:
        服务端返回的 `{server_id, ...}`。
    """
    payload = {
        "server_code": server_code,
        "token": token,
        "agent_version": agent_version,
        **system_info,
    }
    return client.post("/api/v1/agent/register", json=payload)


def send_heartbeat(client: AgentClient, *, server_id: int, agent_version: str) -> dict:
    """发送心跳。

    Args:
        client: 上报客户端。
        server_id: 服务器 ID。
        agent_version: Agent 版本。

    Returns:
        服务端返回的 `{server_id, received_at}`。
    """
    return client.post(
        "/api/v1/agent/heartbeat",
        json={"server_id": server_id, "agent_version": agent_version, "timestamp": _utcnow_iso()},
    )


def send_metrics(client: AgentClient, *, server_id: int, metrics: dict) -> dict:
    """上报一轮指标。

    Args:
        client: 上报客户端。
        server_id: 服务器 ID。
        metrics: 指标字典（不含 server_id/timestamp）。

    Returns:
        服务端返回的 `{server_id, recorded_at}`。
    """
    payload = {"server_id": server_id, "timestamp": _utcnow_iso(), **metrics}
    return client.post("/api/v1/agent/metrics", json=payload)


def send_assets(client: AgentClient, *, server_id: int, assets: dict) -> dict:
    """同步磁盘与网卡资产。

    Args:
        client: 上报客户端。
        server_id: 服务器 ID。
        assets: `{disks, networks}` 字典。

    Returns:
        服务端返回的 `{server_id, synced_at}`。
    """
    payload = {"server_id": server_id, "timestamp": _utcnow_iso(), **assets}
    return client.post("/api/v1/agent/assets", json=payload)


def send_services(client: AgentClient, *, server_id: int, services: list[dict]) -> dict:
    """同步服务状态。

    Args:
        client: 上报客户端。
        server_id: 服务器 ID。
        services: `[{service_name, current_status}]` 列表。

    Returns:
        服务端返回的 `{server_id, synced_at}`。
    """
    return client.post(
        "/api/v1/agent/services",
        json={"server_id": server_id, "timestamp": _utcnow_iso(), "services": services},
    )


def report_task_result(
    client: AgentClient,
    *,
    execution_id: int,
    status: str,
    result_text: str | None = None,
    error_message: str | None = None,
    logs: str | None = None,
) -> dict:
    """回传任务执行结果。

    Args:
        client: 上报客户端。
        execution_id: 执行记录 ID。
        status: SUCCESS/FAILED。
        result_text: 执行结果文本。
        error_message: 错误信息。
        logs: 执行日志。

    Returns:
        服务端返回。
    """
    payload = {
        "execution_id": execution_id,
        "status": status,
        "result_text": result_text,
        "error_message": error_message,
        "logs": logs,
    }
    return client.post("/api/v1/agent/task/result", json=payload)
