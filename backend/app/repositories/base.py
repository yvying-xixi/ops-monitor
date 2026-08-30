from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """泛型仓储基类，提供通用 CRUD、分页与软删除过滤能力。

    Attributes:
        model: 绑定的 ORM 模型类，由子类指定。
        db: SQLAlchemy 会话对象。

    约定：
        - 仓储仅负责数据读写与 flush，事务提交/回滚由 Service 层统一控制。
        - 模型含 `deleted_at` 列时，查询自动追加 `deleted_at IS NULL` 过滤。
        - `list` 分页返回 `(total, items)` 元组。
    """

    model: type[T]

    def __init__(self, db: Session) -> None:
        """初始化仓储。

        Args:
            db: SQLAlchemy 会话对象。
        """
        self.db = db

    @property
    def _has_soft_delete(self) -> bool:
        """模型是否包含软删除标记字段。

        Returns:
            模型含 `deleted_at` 列时返回 True，否则返回 False。
        """
        return "deleted_at" in self.model.__table__.columns

    def _apply_soft_delete(self, stmt):
        """为查询追加软删除过滤条件。

        当模型支持软删除时，追加 `deleted_at IS NULL` 条件，
        仅返回未被软删除的数据。

        Args:
            stmt: 待处理的 SQLAlchemy Select 语句。

        Returns:
            追加软删除条件后的 Select 语句。
        """
        if self._has_soft_delete:
            return stmt.where(self.model.deleted_at.is_(None))
        return stmt

    def _build_conditions(self, filters: dict) -> list:
        """将过滤字段构建为等值条件表达式列表。

        Args:
            filters: 字段名与查询值的映射。

        Returns:
            SQLAlchemy 比较表达式列表。
        """
        return [getattr(self.model, key) == value for key, value in filters.items()]

    def get(self, entity_id: int) -> T | None:
        """按主键查询单个对象。

        Args:
            entity_id: 对象主键 ID。

        Returns:
            匹配的模型对象；不存在时返回 None。
        """
        stmt = self._apply_soft_delete(
            select(self.model).where(self.model.id == entity_id)
        )
        return self.db.scalars(stmt).first()

    def get_by(self, **filters) -> T | None:
        """按多个等值条件查询单个对象。

        Args:
            **filters: 字段名与查询值的映射。

        Returns:
            匹配的第一个模型对象；不存在时返回 None。
        """
        stmt = self._apply_soft_delete(
            select(self.model).where(*self._build_conditions(filters))
        )
        return self.db.scalars(stmt).first()

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        order_by: str | None = None,
        **filters,
    ) -> tuple[int, list[T]]:
        """分页查询对象列表，并统计符合条件的总数。

        Args:
            page: 页码，从 1 开始。
            page_size: 每页数量。
            order_by: 排序字段名，以 `-` 前缀表示降序，如 `-id`。
            **filters: 等值过滤条件。

        Returns:
            元组 `(total, items)`，total 为符合条件的总数，items 为当前页数据。
        """
        base_stmt = select(self.model).where(*self._build_conditions(filters))
        base_stmt = self._apply_soft_delete(base_stmt)

        total = self.db.scalar(
            select(func.count()).select_from(base_stmt.subquery())
        ) or 0

        stmt = base_stmt
        if order_by:
            column = getattr(self.model, order_by.lstrip("-"))
            stmt = stmt.order_by(column.desc() if order_by.startswith("-") else column.asc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(self.db.scalars(stmt).all())
        return total, items

    def list_all(self, **filters) -> list[T]:
        """返回符合条件的所有对象（不分页）。

        Args:
            **filters: 等值过滤条件。

        Returns:
            符合条件的模型对象列表。
        """
        stmt = self._apply_soft_delete(
            select(self.model).where(*self._build_conditions(filters))
        )
        return list(self.db.scalars(stmt).all())

    def create(self, instance: T) -> T:
        """新增单个对象。

        Args:
            instance: 待创建的模型对象。

        Returns:
            创建后的对象（已回填主键）。
        """
        self.db.add(instance)
        self.db.flush()
        return instance

    def create_many(self, instances: list[T]) -> None:
        """批量新增对象。

        Args:
            instances: 待创建的模型对象列表。
        """
        if not instances:
            return
        self.db.add_all(instances)
        self.db.flush()

    def update(self, instance: T, **values) -> T:
        """更新对象的指定字段。

        Args:
            instance: 目标模型对象。
            **values: 字段名与新值的映射。

        Returns:
            更新后的模型对象。
        """
        for key, value in values.items():
            setattr(instance, key, value)
        self.db.flush()
        return instance

    def delete(self, instance: T) -> None:
        """物理删除对象。

        Args:
            instance: 待删除的模型对象。
        """
        self.db.delete(instance)
        self.db.flush()

    def soft_delete(self, instance: T) -> None:
        """软删除对象，将 `deleted_at` 置为当前 UTC 时间。

        仅支持含 `deleted_at` 列的模型。

        Args:
            instance: 待软删除的模型对象。

        Raises:
            ValueError: 模型不支持软删除时抛出。
        """
        if not self._has_soft_delete:
            raise ValueError(f"{self.model.__name__} 不支持软删除")
        instance.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.flush()

    def count(self, **filters) -> int:
        """统计符合条件的对象数量。

        Args:
            **filters: 等值过滤条件。

        Returns:
            符合条件的对象总数。
        """
        stmt = self._apply_soft_delete(
            select(func.count())
            .select_from(self.model)
            .where(*self._build_conditions(filters))
        )
        return self.db.scalar(stmt) or 0
