"""任务分发与调度测试：领取/回传/超时/状态聚合/CRON。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import create_user_with_password

from app.repositories import TaskExecutionRepository
from app.repositories.server_repository import ServiceRepository
from app.repositories.task_repository import TaskLogRepository
from app.schemas.server import ServerCreate
from app.schemas.task import TaskCreate
from app.services.server_service import ServerService
from app.services.task_service import TaskService


_creator_cache: dict = {}


def _creator_id(db):
    key = id(db)
    if key not in _creator_cache:
        _creator_cache[key] = create_user_with_password(db, "task-creator").id
    return _creator_cache[key]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_server(db, code="web-01", service="nginx"):
    suffix = code.split("-")[-1]
    server = ServerService(db).create_server(
        ServerCreate(server_code=code, hostname=code, ip_address=f"10.0.0.{int(suffix) + 10}")
    )
    ServiceRepository(db).upsert_status(server.id, service, "RUNNING")
    return server


def _make_task(db, creator_id, server_ids, service="nginx", action=None, task_type=None):
    if task_type is None:
        task_type = "SERVICE_ACTION" if action else "SERVICE_CHECK"
    payload = TaskCreate(
        task_name="test-task",
        task_type=task_type,
        action=action,
        service_name=service,
        server_ids=server_ids,
    )
    return TaskService(db).create_task(payload, creator_id=creator_id)


def test_dispatch_and_result_success(client, db, admin_headers):
    server = _make_server(db)
    task = _make_task(db, _creator_id(db), [server.id])
    agent_token = ServerService(db).generate_agent_token(server.id).token
    ah = {"Authorization": f"Bearer {agent_token}"}

    # 领取
    resp = client.get("/api/v1/agent/tasks/pending", headers=ah)
    assert resp.status_code == 200
    tasks = resp.json()["data"]
    assert len(tasks) == 1
    assert tasks[0]["action"] == "STATUS"
    execution_id = tasks[0]["execution_id"]

    # 回传成功
    resp = client.post(
        "/api/v1/agent/task/result",
        headers=ah,
        json={"execution_id": execution_id, "status": "SUCCESS", "result_text": "active", "logs": "systemctl is-active nginx -> active"},
    )
    assert resp.status_code == 200

    db.expire_all()
    exec_rec = TaskExecutionRepository(db).get(execution_id)
    assert exec_rec.status == "SUCCESS"
    assert exec_rec.duration_ms is not None
    logs = TaskLogRepository(db).list_by_execution(execution_id)
    assert len(logs) == 1
    # 任务状态聚合为 SUCCESS
    detail = TaskService(db).get_task_detail(task.id)
    assert detail["task"].status == "SUCCESS"


def test_batch_partial_failure_aggregates_failed(client, db, admin_headers):
    s1 = _make_server(db, "web-01")
    s2 = _make_server(db, "web-02")
    task = _make_task(db, _creator_id(db), [s1.id, s2.id])
    token1 = ServerService(db).generate_agent_token(s1.id).token
    token2 = ServerService(db).generate_agent_token(s2.id).token

    r1 = client.get("/api/v1/agent/tasks/pending", headers={"Authorization": f"Bearer {token1}"}).json()["data"][0]
    r2 = client.get("/api/v1/agent/tasks/pending", headers={"Authorization": f"Bearer {token2}"}).json()["data"][0]
    client.post("/api/v1/agent/task/result", headers={"Authorization": f"Bearer {token1}"}, json={"execution_id": r1["execution_id"], "status": "SUCCESS"})
    client.post("/api/v1/agent/task/result", headers={"Authorization": f"Bearer {token2}"}, json={"execution_id": r2["execution_id"], "status": "FAILED", "error_message": "boom"})

    db.expire_all()
    detail = TaskService(db).get_task_detail(task.id)
    assert detail["task"].status == "FAILED"


def test_report_duplicate_rejected(client, db, admin_headers):
    server = _make_server(db)
    _make_task(db, _creator_id(db), [server.id])
    token = ServerService(db).generate_agent_token(server.id).token
    ah = {"Authorization": f"Bearer {token}"}
    exec_id = client.get("/api/v1/agent/tasks/pending", headers=ah).json()["data"][0]["execution_id"]
    payload = {"execution_id": exec_id, "status": "SUCCESS"}
    assert client.post("/api/v1/agent/task/result", headers=ah, json=payload).status_code == 200
    assert client.post("/api/v1/agent/task/result", headers=ah, json=payload).status_code == 400


def test_timeout_scan(db):
    server = _make_server(db)
    creator_id = 1
    task = _make_task(db, _creator_id(db), [server.id])
    # 手动领取并回拨开始时间
    task.status = "RUNNING"
    db.flush()
    exec_rec = TaskExecutionRepository(db).list_by_task(task.id)[0]
    exec_rec.status = "RUNNING"
    exec_rec.started_at = _utcnow() - timedelta(minutes=10)
    db.flush()
    updated = TaskService(db).scan_timeouts()
    assert updated >= 1
    db.expire_all()
    assert TaskExecutionRepository(db).get(exec_rec.id).status == "TIMEOUT"
    detail = TaskService(db).get_task_detail(task.id)
    assert detail["task"].status == "FAILED"  # TIMEOUT 视为失败


def test_cron_task_fire(db):
    server = _make_server(db)
    # cron 表达式：每分钟触发（过去的时间必到期）
    payload = TaskCreate(
        task_name="cron-check",
        task_type="SERVICE_CHECK",
        service_name="nginx",
        server_ids=[server.id],
        schedule_type="CRON",
        cron_expression="* * * * *",
    )
    task = TaskService(db).create_task(payload, creator_id=_creator_id(db))
    assert task.status == "CREATED"  # 定时任务需确认
    TaskService(db).confirm_task(task.id, operator_id=_creator_id(db))
    # 回拨创建时间模拟已到期（cron 每分钟 0 秒触发）
    task.created_at = _utcnow() - timedelta(minutes=2)
    db.flush()
    fired = TaskService(db).fire_due_cron()
    assert fired == 1
    db.expire_all()
    detail = TaskService(db).get_task_detail(task.id)
    assert len(detail["executions"]) == 1
    assert detail["executions"][0]["status"] == "PENDING"
    assert detail["task"].status == "RUNNING"
