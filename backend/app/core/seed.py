"""启动种子数据：幂等初始化角色、权限与初始管理员。"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import SysPermission, SysRole, SysUser
from app.repositories import PermissionRepository, RoleRepository, UserRepository

logger = logging.getLogger(__name__)

DEFAULT_ROLES = [
    {"role_code": "SYSTEM_ADMIN", "role_name": "系统管理员", "description": "拥有系统全部管理权限"},
    {"role_code": "OPS_ENGINEER", "role_name": "运维人员", "description": "负责服务器监控、告警和任务操作"},
    {"role_code": "NORMAL_USER", "role_name": "普通用户", "description": "查看授权服务器和监控数据"},
]

DEFAULT_PERMISSIONS = [
    {"permission_code": "user:manage", "permission_name": "用户管理", "permission_type": "MENU", "path": "/system/users"},
    {"permission_code": "user:list", "permission_name": "用户列表", "permission_type": "API", "path": "/api/v1/users", "method": "GET"},
    {"permission_code": "user:create", "permission_name": "创建用户", "permission_type": "API", "path": "/api/v1/users", "method": "POST"},
    {"permission_code": "user:update", "permission_name": "更新用户", "permission_type": "API", "path": "/api/v1/users/{id}", "method": "PUT"},
    {"permission_code": "user:delete", "permission_name": "删除用户", "permission_type": "API", "path": "/api/v1/users/{id}", "method": "DELETE"},
]


def init_seed_data() -> None:
    """幂等初始化种子数据。

    按角色编码、权限编码、用户名检查存在性，缺失时补建；
    admin 账号密码来自 `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` 配置，
    创建后绑定 `SYSTEM_ADMIN` 角色。
    """
    db = SessionLocal()
    try:
        role_repo = RoleRepository(db)
        permission_repo = PermissionRepository(db)
        user_repo = UserRepository(db)

        created_roles: dict[str, SysRole] = {}
        for item in DEFAULT_ROLES:
            role = role_repo.get_by_code(item["role_code"])
            if role is None:
                role = role_repo.create(SysRole(**item))
                logger.info("种子数据：创建角色 %s", item["role_code"])
            created_roles[item["role_code"]] = role

        for item in DEFAULT_PERMISSIONS:
            if permission_repo.get_by_code(item["permission_code"]) is None:
                permission_repo.create(SysPermission(**item))

        admin = user_repo.get_by_username(settings.SEED_ADMIN_USERNAME)
        if admin is None:
            admin = user_repo.create(
                SysUser(
                    username=settings.SEED_ADMIN_USERNAME,
                    password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
                    nickname="系统管理员",
                    status=1,
                )
            )
            logger.info("种子数据：创建管理员账号 %s", settings.SEED_ADMIN_USERNAME)

        admin_role = created_roles.get("SYSTEM_ADMIN")
        if admin is not None and admin_role is not None:
            user_repo.set_roles(admin.id, [admin_role.id])

        db.commit()
        logger.info("种子数据初始化完成")
    finally:
        db.close()
