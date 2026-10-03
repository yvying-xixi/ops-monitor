"""任务分发与调度测试：领取/回传/超时/状态聚合/CRON。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import create_user_with_password

from app.repositories import TaskExecutionRepository, UserRepository
from app.repositories.server_repository import ServiceRepository
from app.repositories.task_repository import TaskLogRepository
from app.schemas.server import ServerCreate
from app.schemas.task import TaskCreate
from app.services.server_service import ServerService
from app.services.task_service import TaskService


def _creator_id(db):
    """返回创建者用户 id（用例内不存在则创建）。

    不能跨用例缓存：`db` 事务随用例回滚，用户不会真正落库，
    缓存 id 会变成悬空外键（`fk_ops_task_created_by`）。
    """
    repo = UserRepository(db)
    user = repo.get_by_username("task-creator")
    if user is None:
        user = create_user_with_password(db, "task-creator")
    return user.id


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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


def test_report_duplicate_idempotent(client, db, admin_headers):
    server = _make_server(db)
    _make_task(db, _creator_id(db), [server.id])
    token = ServerService(db).generate_agent_token(server.id).token
    ah = {"Authorization": f"Bearer {token}"}
    exec_id = client.get("/api/v1/agent/tasks/pending", headers=ah).json()["data"][0]["execution_id"]
    payload = {"execution_id": exec_id, "status": "SUCCESS"}
    assert client.post("/api/v1/agent/task/result", headers=ah, json=payload).status_code == 200
    # 幂等：重复回传返回 200，状态不重复变更
    assert client.post("/api/v1/agent/task/result", headers=ah, json=payload).status_code == 200
    db.expire_all()
    assert TaskExecutionRepository(db).get(exec_id).status == "SUCCESS"


def test_timeout_scan(db):
    server = _make_server(db)
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


def test_create_task_idempotency_key(db):
    server = _make_server(db)
    creator = _creator_id(db)
    payload = TaskCreate(
        task_name="idem-task",
        task_type="SERVICE_CHECK",
        service_name="nginx",
        server_ids=[server.id],
    )
    service = TaskService(db)
    first = service.create_task(payload, creator_id=creator, idempotency_key="key-1")
    second = service.create_task(payload, creator_id=creator, idempotency_key="key-1")
    assert first.id == second.id
    assert len(TaskExecutionRepository(db).list_by_task(first.id)) == 1


def test_retryable_failure_schedules_next_attempt(db):
    server = _make_server(db)
    task = _make_task(db, _creator_id(db), [server.id])
    execution = TaskExecutionRepository(db).list_by_task(task.id)[0]
    execution.status = "RUNNING"
    db.flush()

    TaskService(db).report_result(
        server,
        execution_id=execution.id,
        status="FAILED",
        error_message="connection refused",
        error_type="NETWORK_ERROR",
    )
    db.expire_all()
    refreshed = TaskExecutionRepository(db).get(execution.id)
    assert refreshed.status == "RETRYING"
    assert refreshed.next_retry_at is not None
    assert TaskService(db).get_task_entity(task.id).status == "RETRYING"

    # 到期后派发下一次尝试（新 execution，attempt=2）
    refreshed.next_retry_at = _utcnow() - timedelta(seconds=1)
    db.flush()
    assert TaskService(db).dispatch_retries() == 1
    db.expire_all()
    attempts = sorted(e.attempt for e in TaskExecutionRepository(db).list_by_task(task.id))
    assert attempts == [1, 2]
    assert TaskService(db).get_task_entity(task.id).status == "RUNNING"


def test_non_retryable_failure_is_terminal(db):
    server = _make_server(db)
    task = _make_task(db, _creator_id(db), [server.id])
    execution = TaskExecutionRepository(db).list_by_task(task.id)[0]
    execution.status = "RUNNING"
    db.flush()

    TaskService(db).report_result(
        server,
        execution_id=execution.id,
        status="FAILED",
        error_message="permission denied",
        error_type="PERMISSION_DENIED",
    )
    db.expire_all()
    assert TaskExecutionRepository(db).get(execution.id).status == "FAILED"
    assert TaskService(db).get_task_entity(task.id).status == "FAILED"


def test_timeout_scan_uses_per_task_timeout(db):
    server = _make_server(db)
    creator = _creator_id(db)
    short = TaskService(db).create_task(
        TaskCreate(
            task_name="short", task_type="SERVICE_CHECK", service_name="nginx",
            server_ids=[server.id], timeout_seconds=60,
        ),
        creator_id=creator,
    )
    long = TaskService(db).create_task(
        TaskCreate(
            task_name="long", task_type="SERVICE_CHECK", service_name="nginx",
            server_ids=[server.id], timeout_seconds=3600,
        ),
        creator_id=creator,
    )
    for task in (short, long):
        task.status = "RUNNING"
        db.flush()
        for execution in TaskExecutionRepository(db).list_by_task(task.id):
            execution.status = "RUNNING"
            execution.started_at = _utcnow() - timedelta(minutes=10)
    db.flush()

    updated = TaskService(db).scan_timeouts()
    assert updated == 1
    db.expire_all()
    assert TaskExecutionRepository(db).list_by_task(short.id)[0].status == "TIMEOUT"
    assert TaskExecutionRepository(db).list_by_task(long.id)[0].status == "RUNNING"


def test_cleanup_old_executions(db):
    server = _make_server(db)
    task = _make_task(db, _creator_id(db), [server.id])
    execution = TaskExecutionRepository(db).list_by_task(task.id)[0]
    execution.status = "SUCCESS"
    execution.finished_at = _utcnow() - timedelta(days=60)
    db.flush()
    TaskLogRepository(db).record(execution.id, "done")

    deleted = TaskService(db).cleanup_executions(30)
    assert deleted == 1
    db.expire_all()
    assert TaskExecutionRepository(db).get(execution.id) is None
    assert TaskLogRepository(db).list_by_execution(execution.id) == []


def test_retry_exhausted_becomes_dead(db):
    server = _make_server(db)
    payload = TaskCreate(
        task_name="dead-task",
        task_type="SERVICE_CHECK",
        service_name="nginx",
        server_ids=[server.id],
        max_attempts=1,
    )
    task = TaskService(db).create_task(payload, creator_id=_creator_id(db))
    execution = TaskExecutionRepository(db).list_by_task(task.id)[0]
    execution.status = "RUNNING"
    db.flush()

    TaskService(db).report_result(
        server,
        execution_id=execution.id,
        status="FAILED",
        error_message="connection reset",
        error_type="NETWORK_ERROR",
    )
    db.expire_all()
    assert TaskExecutionRepository(db).get(execution.id).status == "DEAD"
    assert TaskService(db).get_task_entity(task.id).status == "DEAD"
