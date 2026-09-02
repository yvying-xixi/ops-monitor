"""Agent TaskWorker 测试（mock client 与 executor）。"""

from __future__ import annotations

import json
import threading
from unittest import mock

import httpx

from agent.reporter.client import AgentClient
from agent.worker import TaskWorker


def _make_client(handler) -> AgentClient:
    transport = httpx.MockTransport(handler)
    return AgentClient("http://test.local", "secret", transport=transport)


def test_poll_once_executes_and_reports():
    posted = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": [
                        {
                            "execution_id": 1,
                            "task_id": 10,
                            "action": "STATUS",
                            "service_name": "nginx",
                            "timeout_seconds": 30,
                        }
                    ],
                },
            )
        posted.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = _make_client(handler)
    worker = TaskWorker(client, server_id=1, allowed_services=["nginx"], stop=threading.Event())
    worker.executor = mock.Mock()
    worker.executor.run_action.return_value = (True, "active")

    processed = worker.poll_once()
    assert processed == 1
    worker.executor.run_action.assert_called_once_with("nginx", "STATUS", timeout=30)
    payload = posted[0]
    assert payload["execution_id"] == 1
    assert payload["status"] == "SUCCESS"
    assert payload["result_text"] == "active"


def test_poll_once_logs_action():
    posted = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": [
                        {
                            "execution_id": 2,
                            "task_id": 10,
                            "action": "LOGS",
                            "service_name": "nginx",
                            "timeout_seconds": 30,
                        }
                    ],
                },
            )
        posted.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = _make_client(handler)
    worker = TaskWorker(client, server_id=1, allowed_services=["nginx"], stop=threading.Event())
    worker.executor = mock.Mock()
    worker.executor.fetch_logs.return_value = (True, "log content")

    worker.poll_once()
    worker.executor.fetch_logs.assert_called_once_with("nginx")
    assert posted[0]["logs"] == "log content"


def test_poll_once_reports_failure_on_executor_error():
    posted = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": [
                        {
                            "execution_id": 3,
                            "task_id": 10,
                            "action": "START",
                            "service_name": "docker",
                            "timeout_seconds": 30,
                        }
                    ],
                },
            )
        posted.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0, "data": {}})

    client = _make_client(handler)
    worker = TaskWorker(client, server_id=1, allowed_services=["nginx"], stop=threading.Event())
    worker.executor = mock.Mock()
    worker.executor.run_action.side_effect = ValueError("服务 docker 不在白名单内，拒绝执行")

    worker.poll_once()
    assert posted[0]["status"] == "FAILED"
    assert "白名单" in posted[0]["error_message"]


def test_poll_once_handles_empty():
    client = _make_client(
        lambda request: httpx.Response(200, json={"code": 0, "data": []})
    )
    worker = TaskWorker(client, server_id=1, allowed_services=["nginx"], stop=threading.Event())
    assert worker.poll_once() == 0
