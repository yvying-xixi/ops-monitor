"""自动化任务接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import require_roles
from app.core.database import get_db
from app.models import SysUser
from app.schemas.task import TaskCreate, TaskExecutionOut, TaskOut
from app.services.task_service import TaskService
from app.utils.response import page, success

router = APIRouter(prefix="/tasks", tags=["自动化任务"])

admin_ops = [Depends(require_roles("SYSTEM_ADMIN", "OPS_ENGINEER"))]


@router.get("", summary="任务列表", dependencies=admin_ops)
def list_tasks(
    page_num: int = Query(1, ge=1, alias="page"),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="任务状态"),
    task_type: str | None = Query(None, description="任务类型"),
    db: Session = Depends(get_db),
):
    """分页查询任务列表。"""
    total, items = TaskService(db).list_tasks(page_num, page_size, status, task_type)
    data = page(total, [TaskOut.from_task(t).model_dump() for t in items])
    return success(data=data)


@router.post("", summary="创建任务", status_code=201, dependencies=admin_ops)
def create_task(
    data: TaskCreate,
    current_user: SysUser = Depends(require_roles("SYSTEM_ADMIN", "OPS_ENGINEER")),
    db: Session = Depends(get_db),
):
    """创建运维任务（服务操作/检查/日志）。"""
    task = TaskService(db).create_task(data, creator_id=current_user.id)
    return success(data=TaskOut.from_task(task).model_dump(), message="任务已创建")


@router.get("/{task_id}", summary="任务详情", dependencies=admin_ops)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """任务详情及执行记录。"""
    detail = TaskService(db).get_task_detail(task_id)
    task_out = TaskOut.from_task(detail["task"])
    return success(data={"task": task_out.model_dump(), "executions": detail["executions"]})


@router.post("/{task_id}/confirm", summary="确认任务", dependencies=admin_ops)
def confirm_task(
    task_id: int,
    current_user: SysUser = Depends(require_roles("SYSTEM_ADMIN", "OPS_ENGINEER")),
    db: Session = Depends(get_db),
):
    """确认高风险或定时任务后放行执行。"""
    task = TaskService(db).confirm_task(task_id, operator_id=current_user.id)
    return success(data=TaskOut.from_task(task).model_dump(), message="已确认")


@router.post("/{task_id}/cancel", summary="取消任务", dependencies=admin_ops)
def cancel_task(task_id: int, db: Session = Depends(get_db)):
    """取消未完成的任务。"""
    task = TaskService(db).cancel_task(task_id)
    return success(data=TaskOut.from_task(task).model_dump(), message="已取消")
