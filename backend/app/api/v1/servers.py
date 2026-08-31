"""服务器管理接口（管理员）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import SysUser
from app.schemas.server import AgentTokenResponse, ServerCreate, ServerOut
from app.services.server_service import ServerService
from app.utils.response import page, success

router = APIRouter(prefix="/servers", tags=["服务器管理"])

admin_only = [Depends(require_roles("SYSTEM_ADMIN"))]


@router.post("", summary="创建服务器", status_code=201, dependencies=admin_only)
def create_server(data: ServerCreate, current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """管理员创建服务器资产。"""
    server = ServerService(db).create_server(data, created_by=current_user.id)
    return success(data=ServerOut.model_validate(server).model_dump(), message="创建成功")


@router.get("", summary="服务器列表", dependencies=admin_only)
def list_servers(
    page_num: int = Query(1, ge=1, alias="page"),
    page_size: int = Query(20, ge=1, le=100),
    agent_status: str | None = Query(None, description="ONLINE/WARNING/OFFLINE"),
    db: Session = Depends(get_db),
):
    """分页查询服务器列表。"""
    total, items = ServerService(db).list_servers(page_num, page_size, agent_status)
    data = page(total, [ServerOut.model_validate(s).model_dump() for s in items])
    return success(data=data)


@router.get("/{server_id}", summary="服务器详情", dependencies=admin_only)
def get_server(server_id: int, db: Session = Depends(get_db)):
    """服务器详情。"""
    server = ServerService(db).get_server(server_id)
    return success(data=ServerOut.model_validate(server).model_dump())


@router.post("/{server_id}/agent-token", summary="生成 Agent 注册凭证", dependencies=admin_only)
def generate_agent_token(
    server_id: int,
    token_name: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
):
    """为服务器生成 Agent 注册凭证（明文仅返回一次）。"""
    result: AgentTokenResponse = ServerService(db).generate_agent_token(server_id, token_name)
    return success(data=result.model_dump(), message="凭证已生成，请妥善保存")
