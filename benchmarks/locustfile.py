"""Ops Monitor API 负载测试（Locust）。

覆盖只读热点接口；可选写场景（创建 SERVICE_CHECK 任务）。
用法见 benchmarks/README.md。

环境变量：
    OPS_USERNAME / OPS_PASSWORD   登录账号（默认 admin / admin123456）
    OPS_ENABLE_WRITE=1            启用创建任务写场景
    OPS_SERVER_ID                 指定服务器 ID（默认自动取列表第一条）
"""

from __future__ import annotations

import os
import time

from locust import HttpUser, between, task

USERNAME = os.getenv("OPS_USERNAME", "admin")
PASSWORD = os.getenv("OPS_PASSWORD", "admin123456")
ENABLE_WRITE = os.getenv("OPS_ENABLE_WRITE", "0") == "1"
FIXED_SERVER_ID = os.getenv("OPS_SERVER_ID")


class OpsMonitorUser(HttpUser):
    """模拟管理端用户的只读浏览行为。"""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            name="/api/v1/auth/login",
        )
        token = resp.json()["data"]["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

        self.server_id: int | None = None
        if FIXED_SERVER_ID:
            self.server_id = int(FIXED_SERVER_ID)
        else:
            listing = self.client.get(
                "/api/v1/servers",
                params={"page": 1, "page_size": 1},
                name="/api/v1/servers",
            )
            items = listing.json().get("data", {}).get("items", [])
            self.server_id = items[0]["id"] if items else None

    @task(5)
    def dashboard_overview(self) -> None:
        self.client.get("/api/v1/dashboard/overview")

    @task(5)
    def list_servers(self) -> None:
        self.client.get("/api/v1/servers", params={"page": 1, "page_size": 20})

    @task(3)
    def server_detail(self) -> None:
        if self.server_id:
            self.client.get(f"/api/v1/servers/{self.server_id}")

    @task(3)
    def metrics_latest(self) -> None:
        if self.server_id:
            self.client.get(f"/api/v1/monitor/{self.server_id}/metrics/latest")

    @task(2)
    def metrics_history(self) -> None:
        if self.server_id:
            self.client.get(
                f"/api/v1/monitor/{self.server_id}/metrics/history",
                params={"page": 1, "page_size": 100},
            )

    @task(2)
    def metrics_summary(self) -> None:
        if self.server_id:
            self.client.get(
                f"/api/v1/monitor/{self.server_id}/metrics/summary",
                params={"range": "1h"},
            )

    @task(3)
    def list_alerts(self) -> None:
        self.client.get("/api/v1/alerts", params={"page": 1, "page_size": 20})

    @task(2)
    def list_alert_rules(self) -> None:
        self.client.get("/api/v1/alerts/rules")

    @task(2)
    def list_tasks(self) -> None:
        self.client.get("/api/v1/tasks", params={"page": 1, "page_size": 20})

    @task(1)
    def create_task(self) -> None:
        """写场景：创建只读服务检查任务（需 OPS_ENABLE_WRITE=1）。"""
        if not ENABLE_WRITE or not self.server_id:
            return
        self.client.post(
            "/api/v1/tasks",
            json={
                "task_name": f"load-{int(time.time() * 1000)}",
                "task_type": "SERVICE_CHECK",
                "server_ids": [self.server_id],
            },
            name="/api/v1/tasks [create]",
        )
