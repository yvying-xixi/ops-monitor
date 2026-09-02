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
)
from app.services.agent_service import AgentService
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
