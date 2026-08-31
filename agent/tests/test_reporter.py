"""Agent 上报器 Mock 测试（httpx.MockTransport）。"""

from __future__ import annotations

import json

import httpx
import pytest

from agent.reporter.client import AgentClient, ReporterError
from agent.reporter.report import register, send_assets, send_heartbeat, send_metrics


def _make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    return AgentClient("http://test.local", "secret-token", transport=transport, **kwargs)


def test_agent_client_injects_bearer_header():
    captured = {}

    def handler(request):
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"code": 0, "data": {"ok": True}})

    with _make_client(handler) as client:
        data = client.post("/api/v1/agent/heartbeat", json={})

    assert data == {"ok": True}
    assert captured["headers"]["authorization"] == "Bearer secret-token"


def test_send_metrics_payload():
    captured = {}

    def handler(request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "data": {"server_id": 1}})

    client = _make_client(handler)
    send_metrics(client, server_id=1, metrics={"cpu_usage": 50.0, "load_1m": 1.0})
    assert captured["json"]["server_id"] == 1
    assert captured["json"]["cpu_usage"] == 50.0
    assert "timestamp" in captured["json"]


def test_send_heartbeat_payload():
    captured = {}

    def handler(request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = _make_client(handler)
    send_heartbeat(client, server_id=1, agent_version="1.0.0")
    assert captured["json"]["server_id"] == 1
    assert captured["json"]["agent_version"] == "1.0.0"


def test_register_payload():
    captured = {}

    def handler(request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "data": {"server_id": 7}})

    client = _make_client(handler)
    result = register(
        client,
        server_code="web-01",
        token="secret-token",
        system_info={"hostname": "web-01", "cpu_cores": 4},
        agent_version="1.0.0",
    )
    assert result == {"server_id": 7}
    assert captured["json"]["server_code"] == "web-01"
    assert captured["json"]["token"] == "secret-token"
    assert captured["json"]["cpu_cores"] == 4


def test_send_assets_payload():
    captured = {}

    def handler(request):
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = _make_client(handler)
    send_assets(client, server_id=1, assets={"disks": [], "networks": []})
    assert captured["json"]["server_id"] == 1
    assert captured["json"]["disks"] == []


def test_retry_then_success():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"code": 0, "data": {"retried": True}})

    client = _make_client(handler, retry_max_seconds=4)
    data = client.post("/api/v1/agent/heartbeat", json={})
    assert data == {"retried": True}
    assert calls["count"] == 2


def test_http_error_status_raises():
    def handler(request):
        return httpx.Response(401, json={"code": 40103, "message": "Agent 凭证无效"})

    client = _make_client(handler)
    with pytest.raises(ReporterError):
        client.post("/api/v1/agent/heartbeat", json={})


def test_retry_exhausted_raises():
    def handler(request):
        raise httpx.ConnectError("always down")

    client = _make_client(handler, retry_max_seconds=1)
    with pytest.raises(ReporterError):
        client.post("/api/v1/agent/heartbeat", json={})
