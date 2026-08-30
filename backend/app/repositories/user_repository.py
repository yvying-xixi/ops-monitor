from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models import (
    SysPermission,
    SysRole,
    SysRolePermission,
    SysUser,
    SysUserRole,
)
from app.repositories.base import BaseRepository


def _utcnow() -> datetime:
    """返回当前 UTC 时间（naive，用于写入 DATETIME 字段）。

    Returns:
        不带时区信息的 UTC 时间。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserRepository(BaseRepository[SysUser]):
    """系统用户仓储，提供用户维度的查询与角色绑定操作。"""

    model = SysUser

    def get_by_username(self, username: str) -> SysUser | None:
        """按用户名查询用户。

        Args:
            username: 登录用户名。

        Returns:
            匹配的用户；不存在时返回 None。
        """
        return self.get_by(username=username)

    def get_by_email(self, email: str) -> SysUser | None:
        """按邮箱查询用户。

        Args:
            email: 用户邮箱。

        Returns:
            匹配的用户；不存在时返回 None。
        """
        return self.get_by(email=email)

    def update_last_login(self, user: SysUser, ip: str | None = None) -> SysUser:
        """更新用户最后登录时间与登录 IP。

        Args:
            user: 目标用户对象。
            ip: 登录 IP，可选。

        Returns:
            更新后的用户对象。
        """
        user.last_login_at = _utcnow()
        if ip:
            user.last_login_ip = ip
        self.db.flush()
        return user

    def get_roles_by_user(self, user_id: int) -> list[SysRole]:
        """查询用户绑定的全部角色。

        Args:
            user_id: 用户 ID。

        Returns:
            角色对象列表。
        """
        stmt = (
            select(SysRole)
            .join(SysUserRole, SysUserRole.role_id == SysRole.id)
            .where(SysUserRole.user_id == user_id)
        )
        return list(self.db.scalars(stmt).all())

    def get_role_ids(self, user_id: int) -> list[int]:
        """查询用户绑定的角色 ID 列表。

        Args:
            user_id: 用户 ID。

        Returns:
            角色 ID 列表。
        """
        stmt = select(SysUserRole.role_id).where(SysUserRole.user_id == user_id)
        return list(self.db.scalars(stmt).all())

    def set_roles(self, user_id: int, role_ids: list[int]) -> None:
        """替换用户角色：先清空该用户的全部角色，再写入新角色。

        Args:
            user_id: 用户 ID。
            role_ids: 目标角色 ID 列表。
        """
        self.db.execute(SysUserRole.__table__.delete().where(SysUserRole.user_id == user_id))
        for role_id in set(role_ids):
            self.db.add(SysUserRole(user_id=user_id, role_id=role_id))
        self.db.flush()


class RoleRepository(BaseRepository[SysRole]):
    """角色仓储，提供角色维度的查询与权限绑定操作。"""

    model = SysRole

    def get_by_code(self, role_code: str) -> SysRole | None:
        """按角色编码查询角色。

        Args:
            role_code: 角色编码。

        Returns:
            匹配的角色；不存在时返回 None。
        """
        return self.get_by(role_code=role_code)

    def get_permission_ids(self, role_id: int) -> list[int]:
        """查询角色绑定的权限 ID 列表。

        Args:
            role_id: 角色 ID。

        Returns:
            权限 ID 列表。
        """
        stmt = select(SysRolePermission.permission_id).where(SysRolePermission.role_id == role_id)
        return list(self.db.scalars(stmt).all())

    def set_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        """替换角色权限：先清空该角色的全部权限，再写入新权限。

        Args:
            role_id: 角色 ID。
            permission_ids: 目标权限 ID 列表。
        """
        self.db.execute(SysRolePermission.__table__.delete().where(SysRolePermission.role_id == role_id))
        for permission_id in set(permission_ids):
            self.db.add(SysRolePermission(role_id=role_id, permission_id=permission_id))
        self.db.flush()


class PermissionRepository(BaseRepository[SysPermission]):
    """权限仓储，提供权限码查询、菜单树素材与角色权限码集合。"""

    model = SysPermission

    def get_by_code(self, permission_code: str) -> SysPermission | None:
        """按权限编码查询权限。

        Args:
            permission_code: 权限编码。

        Returns:
            匹配的权限；不存在时返回 None。
        """
        return self.get_by(permission_code=permission_code)

    def list_tree(self) -> list[SysPermission]:
        """查询全部启用权限，按 id 升序排列。

        返回扁平的权限列表，树形组装由 Service 层完成。

        Returns:
            启用状态下的权限对象列表。
        """
        stmt = (
            select(SysPermission)
            .where(SysPermission.status == 1)
            .order_by(SysPermission.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_codes_by_role(self, role_id: int) -> list[str]:
        """查询角色拥有的权限编码集合，用于接口鉴权。

        Args:
            role_id: 角色 ID。

        Returns:
            权限编码列表。
        """
        stmt = (
            select(SysPermission.permission_code)
            .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
            .where(SysRolePermission.role_id == role_id, SysPermission.status == 1)
        )
        return list(self.db.scalars(stmt).all())
