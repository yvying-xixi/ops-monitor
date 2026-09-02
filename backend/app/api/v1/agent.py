"""Agent 上报接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.v1.deps import get_agent_server
from app.core.database import get_db
from app.models import OpsServer
from app.schemas.agent import (
    AssetsRequest,
    HeartbeatRequest,
    MetricsRequest,
    RegisterRequest,
    ServicesRequest,
    TaskResultRequest,
)
from app.services.agent_service import AgentService
from app.services.task_service import TaskService
from app.utils.request import get_client_ip
from app.utils.response import success

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/register", summary="Agent 注册", description="使用 server_code + token 注册并回写系统信息。")
def register(
    data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Agent 注册接口。"""
    result = AgentService(db).register(data, ip=get_client_ip(request))
    return success(data=result, message="注册成功")


@router.post("/heartbeat", summary="Agent 心跳")
def heartbeat(
    data: HeartbeatRequest,
    request: Request,
    server: OpsServer = Depends(get_agent_server),
    db: Session = Depends(get_db),
):
    """Agent 心跳接口。"""
    result = AgentService(db).heartbeat(server, data, ip=get_client_ip(request))
    return success(data=result)


@router.post("/metrics", summary="Agent 指标上报")
def ingest_metrics(
    data: MetricsRequest,
    server: OpsServer = Depends(get_agent_server),
    db: Session = Depends(get_db),
):
    """Agent 指标上报接口。"""
    result = AgentService(db).ingest_metrics(server, data)
    return success(data=result)


@router.post("/assets", summary="Agent 资产同步")
def sync_assets(
    data: AssetsRequest,
    server: OpsServer = Depends(get_agent_server),
    db: Session = Depends(get_db),
):
    """Agent 磁盘/网卡资产同步接口。"""
    result = AgentService(db).sync_assets(server, data)
    return success(data=result)


@router.post("/services", summary="Agent 服务状态同步")
def sync_services(
    data: ServicesRequest,
    server: OpsServer = Depends(get_agent_server),
    db: Session = Depends(get_db),
):
    """Agent 服务状态同步接口。"""
    result = AgentService(db).sync_services(server, data)
    return success(data=result)


@router.get("/tasks/pending", summary="Agent 拉取待执行任务")
def fetch_pending_tasks(
    server: OpsServer = Depends(get_agent_server),
    db: Session = Depends(get_db),
):
    """Agent 轮询拉取本服务器待执行任务（领取后置 RUNNING）。"""
    tasks = TaskService(db).fetch_pending(server)
    return success(data=tasks)


@router.post("/task/result", summary="Agent 回传任务执行结果")
def report_task_result(
    data: TaskResultRequest,
    server: OpsServer = Depends(get_agent_server),
    db: Session = Depends(get_db),
):
    """Agent 回传任务执行结果。"""
    TaskService(db).report_result(
        server,
        execution_id=data.execution_id,
        status=data.status,
        exit_code=data.exit_code,
        result_text=data.result_text,
        error_message=data.error_message,
        logs=data.logs,
    )
    return success(message="已记录")
