"""角色管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_roles
from app.core.database import get_db
from app.repositories import RoleRepository
from app.utils.response import success

router = APIRouter(prefix="/roles", tags=["角色管理"])

admin_only = [Depends(require_roles("SYSTEM_ADMIN"))]


@router.get("", summary="角色列表", dependencies=admin_only)
def list_roles(db: Session = Depends(get_db)):
    """查询全部启用角色（供用户管理下拉选择）。"""
    roles = RoleRepository(db).list_all(status=1)
    return success(
        data=[
            {"id": r.id, "role_code": r.role_code, "role_name": r.role_name}
            for r in roles
        ]
    )
