from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SysUser(Base):
    __tablename__ = "sys_user"
    __table_args__ = (
        UniqueConstraint("username", name="uk_sys_user_username"),
        UniqueConstraint("email", name="uk_sys_user_email"),
        Index("idx_sys_user_status", "status"),
        Index("idx_sys_user_deleted_at", "deleted_at"),
        {"comment": "系统用户表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(64), comment="登录用户名")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    nickname: Mapped[str | None] = mapped_column(String(64), comment="用户昵称")
    email: Mapped[str | None] = mapped_column(String(128), comment="邮箱")
    phone: Mapped[str | None] = mapped_column(String(32), comment="手机号")
    status: Mapped[int] = mapped_column(TINYINT, server_default=text("1"), comment="状态：0禁用，1启用")
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="最后登录时间")
    last_login_ip: Mapped[str | None] = mapped_column(String(64), comment="最后登录IP")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), comment="软删除时间")

    roles: Mapped[list[SysRole]] = relationship(
        "SysRole", secondary="sys_user_role", back_populates="users"
    )


class SysRole(Base):
    __tablename__ = "sys_role"
    __table_args__ = (
        UniqueConstraint("role_code", name="uk_sys_role_code"),
        Index("idx_sys_role_status", "status"),
        {"comment": "系统角色表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="角色ID")
    role_code: Mapped[str] = mapped_column(String(64), comment="角色编码")
    role_name: Mapped[str] = mapped_column(String(64), comment="角色名称")
    description: Mapped[str | None] = mapped_column(String(255), comment="角色描述")
    status: Mapped[int] = mapped_column(TINYINT, server_default=text("1"), comment="状态：0禁用，1启用")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )

    users: Mapped[list[SysUser]] = relationship(
        "SysUser", secondary="sys_user_role", back_populates="roles"
    )
    permissions: Mapped[list[SysPermission]] = relationship(
        "SysPermission", secondary="sys_role_permission", back_populates="roles"
    )


class SysPermission(Base):
    __tablename__ = "sys_permission"
    __table_args__ = (
        UniqueConstraint("permission_code", name="uk_sys_permission_code"),
        Index("idx_sys_permission_parent_id", "parent_id"),
        Index("idx_sys_permission_type_status", "permission_type", "status"),
        {"comment": "系统权限表"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="权限ID")
    permission_code: Mapped[str] = mapped_column(String(128), comment="权限编码")
    permission_name: Mapped[str] = mapped_column(String(128), comment="权限名称")
    permission_type: Mapped[str] = mapped_column(String(16), comment="权限类型：MENU/API/BUTTON")
    path: Mapped[str | None] = mapped_column(String(255), comment="前端路由或接口路径")
    method: Mapped[str | None] = mapped_column(String(16), comment="HTTP方法")
    parent_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_permission.id", name="fk_sys_permission_parent"),
        comment="父权限ID",
    )
    status: Mapped[int] = mapped_column(TINYINT, server_default=text("1"), comment="状态：0禁用，1启用")
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
    )

    parent: Mapped[SysPermission | None] = relationship(
        "SysPermission", remote_side="SysPermission.id", back_populates="children"
    )
    children: Mapped[list[SysPermission]] = relationship(
        "SysPermission", back_populates="parent"
    )
    roles: Mapped[list[SysRole]] = relationship(
        "SysRole", secondary="sys_role_permission", back_populates="permissions"
    )


class SysUserRole(Base):
    __tablename__ = "sys_user_role"
    __table_args__ = (
        Index("idx_sys_user_role_role_id", "role_id"),
        {"comment": "用户角色关联表"},
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_user.id", name="fk_sys_user_role_user"),
        primary_key=True,
        comment="用户ID",
    )
    role_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_role.id", name="fk_sys_user_role_role"),
        primary_key=True,
        comment="角色ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )


class SysRolePermission(Base):
    __tablename__ = "sys_role_permission"
    __table_args__ = (
        Index("idx_sys_role_permission_permission_id", "permission_id"),
        {"comment": "角色权限关联表"},
    )

    role_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_role.id", name="fk_sys_role_permission_role"),
        primary_key=True,
        comment="角色ID",
    )
    permission_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("sys_permission.id", name="fk_sys_role_permission_permission"),
        primary_key=True,
        comment="权限ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)")
    )
