"""自动化任务 Agent → API → DB 全链路 E2E 测试。

启动真实 uvicorn（关闭种子、自建 admin），创建服务器并注册真实 Agent，
提交「服务检查（STATUS，只读）」任务，用真实 TaskWorker 轮询执行，
断言执行 SUCCESS 且 ops_task_log 落库，最后自清理。
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

from agent.collector import collect_system_info  # noqa: E402
from agent.reporter.client import AgentClient  # noqa: E402
from agent.reporter.report import register  # noqa: E402
from agent.worker import TaskWorker  # noqa: E402

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
    OpsServerService,
    OpsTask,
    OpsTaskExecution,
    OpsTaskLog,
    OpsTaskTarget,
    SysLoginLog,
    SysOperationLog,
    SysRole,
    SysUser,
    SysUserRole,
)

SERVER_CODE = "task-e2e-01"
ADMIN_USER = "task-e2e-admin"
ADMIN_PASS = "task-e2e-pass"
CHECK_SERVICE = "docker"  # 本机活跃的 systemd 服务（只读 STATUS）


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _ServerThread(threading.Thread):
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
                username=ADMIN_USER, password_hash=hash_password(ADMIN_PASS), status=1
            )
            db.add(admin)
            db.flush()
            db.add(SysUserRole(user_id=admin.id, role_id=role.id))
        db.commit()
        return admin.id, role_created
    finally:
        db.close()


def _cleanup(admin_id: int, role_created: bool) -> None:
    db = SessionLocal()
    try:
        server = db.scalars(
            select(OpsServer).where(OpsServer.server_code == SERVER_CODE)
        ).first()
        if server is not None:
            sid = server.id
            task_ids = db.scalars(
                select(OpsTask.id).where(
                    OpsTask.id.in_(select(OpsTaskExecution.task_id).where(OpsTaskExecution.server_id == sid))
                )
            ).all()
            for task_id in task_ids:
                db.execute(delete(OpsTaskLog).where(
                    OpsTaskLog.execution_id.in_(
                        select(OpsTaskExecution.id).where(OpsTaskExecution.task_id == task_id)
                    )
                ))
                db.execute(delete(OpsTaskExecution).where(OpsTaskExecution.task_id == task_id))
                db.execute(delete(OpsTaskTarget).where(OpsTaskTarget.task_id == task_id))
                db.execute(delete(OpsTask).where(OpsTask.id == task_id))
            db.execute(delete(OpsAgentHeartbeat).where(OpsAgentHeartbeat.server_id == sid))
            db.execute(delete(OpsAgentToken).where(OpsAgentToken.server_id == sid))
            db.execute(delete(MonitorServerMetric).where(MonitorServerMetric.server_id == sid))
            db.execute(delete(OpsServerDisk).where(OpsServerDisk.server_id == sid))
            db.execute(delete(OpsServerNetwork).where(OpsServerNetwork.server_id == sid))
            db.execute(delete(OpsServerService).where(OpsServerService.server_id == sid))
            db.execute(delete(SysOperationLog).where(SysOperationLog.server_id == sid))
            db.execute(delete(OpsServer).where(OpsServer.id == sid))
        db.execute(delete(SysLoginLog).where(SysLoginLog.user_id == admin_id))
        db.execute(delete(SysOperationLog).where(SysOperationLog.user_id == admin_id))
        db.execute(delete(SysUserRole).where(SysUserRole.user_id == admin_id))
        db.execute(delete(SysUser).where(SysUser.id == admin_id))
        if role_created:
            db.execute(delete(SysRole).where(SysRole.role_code == "SYSTEM_ADMIN"))
        db.commit()
    finally:
        db.close()


def test_task_e2e():
    original_seed = settings.SEED_INIT_DATA
    settings.SEED_INIT_DATA = False
    admin_id, role_created = _seed_admin()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    thread = _ServerThread(port)
    thread.start()
    try:
        _wait_ready(base_url)

        # 1. admin 登录，创建服务器并生成 Agent 凭证
        headers = {
            "Authorization": "Bearer "
            + httpx.post(
                f"{base_url}/api/v1/auth/login",
                json={"username": ADMIN_USER, "password": ADMIN_PASS},
            ).json()["data"]["access_token"]
        }
        resp = httpx.post(
            f"{base_url}/api/v1/servers",
            headers=headers,
            json={"server_code": SERVER_CODE, "hostname": SERVER_CODE, "ip_address": "10.0.0.88"},
        )
        server_id = resp.json()["data"]["id"]
        agent_token = httpx.post(
            f"{base_url}/api/v1/servers/{server_id}/agent-token", headers=headers
        ).json()["data"]["token"]

        # 2. 真实 Agent 注册
        client = AgentClient(base_url, agent_token)
        register(
            client,
            server_code=SERVER_CODE,
            token=agent_token,
            system_info=collect_system_info(),
            agent_version="1.0.0",
        )

        # 3. 创建「服务检查 STATUS（只读）」任务
        resp = httpx.post(
            f"{base_url}/api/v1/tasks",
            headers=headers,
            json={
                "task_name": "检查 docker",
                "task_type": "SERVICE_CHECK",
                "service_name": CHECK_SERVICE,
                "server_ids": [server_id],
            },
        )
        assert resp.status_code == 201
        task_id = resp.json()["data"]["id"]

        # 4. 真实 TaskWorker 轮询领取并执行
        worker = TaskWorker(
            client, server_id=server_id, allowed_services=[CHECK_SERVICE],
            poll_interval=1, stop=__import__("threading").Event(),
        )
        worker.poll_once()
        client.close()

        # 5. 断言：执行 SUCCESS + 任务日志落库
        db = SessionLocal()
        try:
            exec_rec = db.scalars(
                select(OpsTaskExecution).where(OpsTaskExecution.task_id == task_id)
            ).first()
            assert exec_rec is not None, "执行记录未创建"
            assert exec_rec.status == "SUCCESS", f"执行结果 {exec_rec.status}"
            logs = db.scalars(
                select(OpsTaskLog).where(OpsTaskLog.execution_id == exec_rec.id)
            ).all()
            assert len(logs) >= 1, "任务日志未落库"
            task = db.get(OpsTask, task_id)
            assert task.status == "SUCCESS"
        finally:
            db.close()
    finally:
        thread.stop()
        thread.join(timeout=10)
        _cleanup(admin_id, role_created)
        settings.SEED_INIT_DATA = original_seed
