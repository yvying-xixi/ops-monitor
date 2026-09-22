"""Agent 上报接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.v1.deps import get_agent_server
from app.core.database import get_db
from app.exceptions import AppException, ErrorCode
from app.models import OpsServer
from app.schemas.agent import (
    AssetsRequest,
    HeartbeatRequest,
    MetricsRequest,
    RegisterRequest,
    ServicesRequest,
    TaskResultRequest,
)
from app.services.agent_package import (
    AgentPackageError,
    build_agent_package,
    read_install_script,
)
from app.services.agent_service import AgentService
from app.services.task_service import TaskService
from app.utils.request import get_client_ip
from app.utils.response import success

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.get("/package", summary="下载 Agent 安装包", include_in_schema=True)
def download_agent_package():
    """下载 Agent 安装包（tar.gz，含源码、install.sh 与 systemd 模板）。"""
    try:
        content, filename = build_agent_package()
    except AgentPackageError as exc:
        raise AppException(ErrorCode.NOT_FOUND, str(exc), http_status=404) from exc
    return Response(
        content=content,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/install.sh", summary="获取 Agent 安装脚本", response_class=PlainTextResponse)
def get_install_script():
    """返回 Agent 一键安装脚本内容。"""
    try:
        content = read_install_script()
    except AgentPackageError as exc:
        raise AppException(ErrorCode.NOT_FOUND, str(exc), http_status=404) from exc
    return PlainTextResponse(content, media_type="text/x-shellscript")



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
