"""用户管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import require_roles
from app.core.database import get_db
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.user_service import UserService
from app.utils.response import page, success

router = APIRouter(prefix="/users", tags=["用户管理"])

admin_only = [Depends(require_roles("SYSTEM_ADMIN"))]


@router.get("", summary="用户分页列表", dependencies=admin_only)
def list_users(
    page_num: int = Query(1, ge=1, alias="page"),
    page_size: int = Query(20, ge=1, le=100),
    username: str | None = Query(None, max_length=64),
    status: int | None = Query(None, ge=0, le=1),
    db: Session = Depends(get_db),
):
    """分页查询用户列表。

    Returns:
        统一响应，data 为 `{total, items}`，items 为 UserOut 列表。
    """
    service = UserService(db)
    total, items = service.list_users(page_num, page_size, username, status)
    data = page(total, [UserOut.model_validate(u).model_dump() for u in items])
    return success(data=data)


@router.post("", summary="创建用户", status_code=201, dependencies=admin_only)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    """创建用户。

    Returns:
        统一响应，data 为创建的 UserOut。
    """
    user = UserService(db).create_user(data)
    return success(data=UserOut.model_validate(user).model_dump(), message="创建成功")


@router.get("/{user_id}", summary="用户详情", dependencies=admin_only)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """按 ID 查询用户。

    Returns:
        统一响应，data 为 UserOut。
    """
    user = UserService(db).get_user(user_id)
    return success(data=UserOut.model_validate(user).model_dump())


@router.put("/{user_id}", summary="更新用户", dependencies=admin_only)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    """更新用户信息。

    Returns:
        统一响应，data 为更新后的 UserOut。
    """
    user = UserService(db).update_user(user_id, data)
    return success(data=UserOut.model_validate(user).model_dump(), message="更新成功")


@router.delete("/{user_id}", summary="删除用户", dependencies=admin_only)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """软删除用户。

    Returns:
        统一响应，message 提示删除成功。
    """
    UserService(db).delete_user(user_id)
    return success(message="删除成功")
