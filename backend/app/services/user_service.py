"""用户管理服务：用户 CRUD 与角色分配。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.exceptions import AppException, ErrorCode
from app.models import SysUser
from app.repositories import RoleRepository, UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """用户管理业务逻辑，事务提交统一在此层完成。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.role_repo = RoleRepository(db)

    def create_user(self, data: UserCreate) -> SysUser:
        """创建用户并分配角色。

        Args:
            data: 创建用户请求模型。

        Returns:
            创建成功的用户对象。

        Raises:
            AppException: 用户名已存在（40901）、邮箱已使用（40902）、角色不存在（40402）。
        """
        if self.user_repo.get_by_username(data.username):
            raise AppException(ErrorCode.USERNAME_EXISTS, "用户名已存在", http_status=409)
        if data.email and self.user_repo.get_by_email(data.email):
            raise AppException(ErrorCode.EMAIL_EXISTS, "邮箱已被使用", http_status=409)
        self._validate_roles(data.role_ids)

        user = SysUser(
            username=data.username,
            password_hash=hash_password(data.password),
            nickname=data.nickname,
            email=data.email,
            phone=data.phone,
            status=1,
        )
        self.user_repo.create(user)
        if data.role_ids:
            self.user_repo.set_roles(user.id, data.role_ids)
        self.db.commit()
        return user

    def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        username: str | None = None,
        status: int | None = None,
    ) -> tuple[int, list[SysUser]]:
        """分页查询用户列表。

        Args:
            page: 页码。
            page_size: 每页数量。
            username: 用户名精确过滤，可选。
            status: 账号状态过滤，可选。

        Returns:
            元组 (total, items)。
        """
        filters: dict = {}
        if username:
            filters["username"] = username
        if status is not None:
            filters["status"] = status
        return self.user_repo.list(page=page, page_size=page_size, order_by="-id", **filters)

    def get_user(self, user_id: int) -> SysUser:
        """按 ID 查询用户。

        Args:
            user_id: 用户 ID。

        Returns:
            用户对象。

        Raises:
            AppException: 用户不存在（40401）。
        """
        user = self.user_repo.get(user_id)
        if user is None:
            raise AppException(ErrorCode.USER_NOT_FOUND, "用户不存在", http_status=404)
        return user

    def update_user(self, user_id: int, data: UserUpdate) -> SysUser:
        """更新用户信息与角色。

        Args:
            user_id: 用户 ID。
            data: 更新请求模型（仅更新显式传入的字段）。

        Returns:
            更新后的用户对象。

        Raises:
            AppException: 用户不存在（40401）、邮箱已被他人使用（40902）、角色不存在（40402）。
        """
        user = self.get_user(user_id)
        values = data.model_dump(exclude_unset=True)
        role_ids = values.pop("role_ids", None)

        password = values.pop("password", None)
        if password:
            values["password_hash"] = hash_password(password)

        email = values.get("email")
        if email and email != user.email:
            existing = self.user_repo.get_by_email(email)
            if existing and existing.id != user_id:
                raise AppException(ErrorCode.EMAIL_EXISTS, "邮箱已被使用", http_status=409)

        if role_ids is not None:
            self._validate_roles(role_ids)

        self.user_repo.update(user, **values)
        if role_ids is not None:
            self.user_repo.set_roles(user.id, role_ids)
        self.db.commit()
        return user

    def delete_user(self, user_id: int) -> None:
        """软删除用户。

        Args:
            user_id: 用户 ID。

        Raises:
            AppException: 用户不存在（40401）。
        """
        user = self.get_user(user_id)
        self.user_repo.soft_delete(user)
        self.db.commit()

    def _validate_roles(self, role_ids: list[int]) -> None:
        """校验角色 ID 均存在。

        Args:
            role_ids: 角色 ID 列表。

        Raises:
            AppException: 存在不存在的角色（40402）。
        """
        for role_id in set(role_ids):
            if self.role_repo.get(role_id) is None:
                raise AppException(
                    ErrorCode.ROLE_NOT_FOUND, f"角色不存在: {role_id}", http_status=404
                )
