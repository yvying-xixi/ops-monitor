"""Agent → API → DB 全链路 E2E 测试。

启动真实 uvicorn 服务（关闭种子数据、自建 admin），用真实 Agent 采集器与
上报器走完整 HTTP 协议，执行「管理员建服务器 → 生成凭证 → 注册 → 心跳 →
指标 → 资产」流程，断言数据库落库后自清理，不影响其他测试。
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

import httpx
from sqlalchemy import delete, select

# 仓库根目录入 path，使 `agent` 包可导入
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent.collector import collect_assets, collect_metrics, collect_system_info  # noqa: E402
from agent.reporter.client import AgentClient  # noqa: E402
from agent.reporter.report import register, send_assets, send_heartbeat, send_metrics  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    MonitorServerMetric,
    OpsAgentHeartbeat,
    OpsAgentToken,
    OpsServer,
    OpsServerDisk,
    OpsServerNetwork,
    SysLoginLog,
    SysOperationLog,
    SysRole,
    SysUser,
    SysUserRole,
)
from app.schemas.server import ServerCreate  # noqa: E402
from app.services.server_service import ServerService  # noqa: E402

SERVER_CODE = "e2e-01"
ADMIN_USER = "e2e-admin"
ADMIN_PASS = "e2e-admin-pass"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _ServerThread(threading.Thread):
    """在后台线程运行 uvicorn 服务。"""

    def __init__(self, port: int) -> None:
        super().__init__(daemon=True)
        import uvicorn

        self.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


def _wait_ready(base_url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/api/v1/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise TimeoutError("服务启动超时")


def _seed_admin() -> tuple[int, bool]:
    """在真实库创建 E2E 专用 admin 用户（幂等），返回 (admin_id, 是否创建了角色)。"""
    db = SessionLocal()
    try:
        role = db.scalars(
            select(SysRole).where(SysRole.role_code == "SYSTEM_ADMIN")
        ).first()
        role_created = role is None
        if role is None:
            role = SysRole(role_code="SYSTEM_ADMIN", role_name="系统管理员")
            db.add(role)
            db.flush()

        admin = db.scalars(select(SysUser).where(SysUser.username == ADMIN_USER)).first()
        if admin is None:
            admin = SysUser(
                username=ADMIN_USER,
                password_hash=hash_password(ADMIN_PASS),
                nickname="E2E Admin",
                status=1,
            )
            db.add(admin)
            db.flush()
            db.add(SysUserRole(user_id=admin.id, role_id=role.id))
        db.commit()
        return admin.id, role_created
    finally:
        db.close()


def _cleanup(admin_id: int, role_created: bool) -> None:
    """清理 E2E 测试写入的数据，恢复库的初始状态。"""
    db = SessionLocal()
    try:
        server = db.scalars(
            select(OpsServer).where(OpsServer.server_code == SERVER_CODE)
        ).first()
        if server is not None:
            server_id = server.id
            db.execute(delete(SysOperationLog).where(SysOperationLog.server_id == server_id))
            db.execute(delete(OpsAgentToken).where(OpsAgentToken.server_id == server_id))
            db.execute(delete(OpsAgentHeartbeat).where(OpsAgentHeartbeat.server_id == server_id))
            db.execute(delete(MonitorServerMetric).where(MonitorServerMetric.server_id == server_id))
            db.execute(delete(OpsServerDisk).where(OpsServerDisk.server_id == server_id))
            db.execute(delete(OpsServerNetwork).where(OpsServerNetwork.server_id == server_id))
            db.execute(delete(OpsServer).where(OpsServer.id == server_id))

        db.execute(delete(SysLoginLog).where(SysLoginLog.user_id == admin_id))
        db.execute(delete(SysOperationLog).where(SysOperationLog.user_id == admin_id))
        db.execute(delete(SysUserRole).where(SysUserRole.user_id == admin_id))
        db.execute(delete(SysUser).where(SysUser.id == admin_id))
        if role_created:
            db.execute(delete(SysRole).where(SysRole.role_code == "SYSTEM_ADMIN"))
        db.commit()
    finally:
        db.close()


def test_agent_e2e():
    original_seed = settings.SEED_INIT_DATA
    settings.SEED_INIT_DATA = False
    admin_id, role_created = _seed_admin()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    thread = _ServerThread(port)
    thread.start()
    try:
        _wait_ready(base_url)

        # 1. E2E admin 登录
        login = httpx.post(
            f"{base_url}/api/v1/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        assert login.status_code == 200
        token = login.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. 管理员创建服务器并生成注册凭证
        resp = httpx.post(
            f"{base_url}/api/v1/servers",
            headers=headers,
            json={"server_code": SERVER_CODE, "hostname": SERVER_CODE, "ip_address": "10.0.0.99"},
        )
        assert resp.status_code == 201
        server_id = resp.json()["data"]["id"]
        resp = httpx.post(f"{base_url}/api/v1/servers/{server_id}/agent-token", headers=headers)
        assert resp.status_code == 200
        agent_token = resp.json()["data"]["token"]

        # 3. 真实 Agent 走完整协议
        client = AgentClient(base_url, agent_token)
        registered = register(
            client,
            server_code=SERVER_CODE,
            token=agent_token,
            system_info=collect_system_info(),
            agent_version="1.0.0",
        )
        assert registered["server_id"] == server_id

        send_heartbeat(client, server_id=server_id, agent_version="1.0.0")
        send_metrics(client, server_id=server_id, metrics=collect_metrics())
        send_assets(client, server_id=server_id, assets=collect_assets())
        client.close()

        # 4. 断言真实库落库结果
        db = SessionLocal()
        try:
            server = db.scalars(
                select(OpsServer).where(OpsServer.server_code == SERVER_CODE)
            ).first()
            assert server is not None
            assert server.agent_status == "ONLINE"
            assert server.registered_at is not None
            assert server.cpu_cores > 0

            metrics = db.scalars(
                select(MonitorServerMetric).where(MonitorServerMetric.server_id == server_id)
            ).all()
            assert len(metrics) == 1
            assert 0 <= metrics[0].cpu_usage <= 100

            heartbeats = db.scalars(
                select(OpsAgentHeartbeat).where(OpsAgentHeartbeat.server_id == server_id)
            ).all()
            assert len(heartbeats) >= 1

            disks = db.scalars(
                select(OpsServerDisk).where(OpsServerDisk.server_id == server_id)
            ).all()
            assert len(disks) >= 1
        finally:
            db.close()
    finally:
        thread.stop()
        thread.join(timeout=10)
        _cleanup(admin_id, role_created)
        settings.SEED_INIT_DATA = original_seed
