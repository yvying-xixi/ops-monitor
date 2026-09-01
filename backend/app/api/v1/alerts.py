"""告警中心接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import SysUser
from app.schemas.alert import RuleCreate, RuleOut, RuleUpdate
from app.services.alert_service import AlertService
from app.utils.response import page, success

router = APIRouter(prefix="/alerts", tags=["告警中心"])

admin_ops = [Depends(require_roles("SYSTEM_ADMIN", "OPS_ENGINEER"))]
admin_only = [Depends(require_roles("SYSTEM_ADMIN"))]


@router.get("", summary="告警事件列表")
def list_alerts(
    page_num: int = Query(1, ge=1, alias="page"),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="PENDING/FIRING/ACKNOWLEDGED/RESOLVED"),
    severity: str | None = Query(None, description="WARNING/CRITICAL"),
    server_id: int | None = Query(None),
    active: bool | None = Query(None, description="仅活动告警"),
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询告警事件。"""
    total, items = AlertService(db).list_events(
        page_num, page_size, status=status, severity=severity, server_id=server_id, active=active
    )
    return success(data=page(total, items))


@router.get("/rules", summary="告警规则列表")
def list_rules(
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询全部告警规则。"""
    rules = AlertService(db).list_rules()
    return success(data=[RuleOut.model_validate(r).model_dump() for r in rules])


@router.get("/{event_id}", summary="告警事件详情")
def get_event(
    event_id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询告警事件及状态流转日志。"""
    return success(data=AlertService(db).get_event(event_id))


@router.post("/{event_id}/ack", summary="确认告警")
def acknowledge(
    event_id: int,
    current_user: SysUser = Depends(require_roles("SYSTEM_ADMIN", "OPS_ENGINEER")),
    db: Session = Depends(get_db),
):
    """确认告警事件。"""
    result = AlertService(db).acknowledge(event_id, operator_id=current_user.id)
    return success(data=result, message="已确认")


@router.post("/{event_id}/resolve", summary="恢复告警")
def resolve(
    event_id: int,
    current_user: SysUser = Depends(require_roles("SYSTEM_ADMIN", "OPS_ENGINEER")),
    db: Session = Depends(get_db),
):
    """人工恢复告警事件。"""
    result = AlertService(db).resolve(event_id, operator_id=current_user.id)
    return success(data=result, message="已恢复")


@router.post("/rules", summary="创建告警规则", status_code=201, dependencies=admin_only)
def create_rule(
    data: RuleCreate,
    current_user: SysUser = Depends(require_roles("SYSTEM_ADMIN")),
    db: Session = Depends(get_db),
):
    """创建告警规则。"""
    rule = AlertService(db).create_rule(data, created_by=current_user.id)
    return success(data=RuleOut.model_validate(rule).model_dump(), message="创建成功")


@router.put("/rules/{rule_id}", summary="更新告警规则", dependencies=admin_only)
def update_rule(
    rule_id: int,
    data: RuleUpdate,
    db: Session = Depends(get_db),
):
    """更新告警规则。"""
    rule = AlertService(db).update_rule(rule_id, data)
    return success(data=RuleOut.model_validate(rule).model_dump(), message="更新成功")


@router.delete("/rules/{rule_id}", summary="删除告警规则", dependencies=admin_only)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
):
    """删除告警规则。"""
    AlertService(db).delete_rule(rule_id)
    return success(message="删除成功")
