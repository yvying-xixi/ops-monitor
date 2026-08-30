"""统一响应辅助函数。"""

from __future__ import annotations

from typing import Any


def success(data: Any = None, message: str = "ok") -> dict:
    """构造成功响应体。

    Args:
        data: 业务数据，可选。
        message: 提示信息。

    Returns:
        `{code: 0, message, data}` 字典。
    """
    return {"code": 0, "message": message, "data": data}


def page(total: int, items: list[Any]) -> dict:
    """构造分页数据体，供 `success(data=page(...))` 使用。

    Args:
        total: 符合条件的记录总数。
        items: 当前页数据列表。

    Returns:
        `{total, items}` 字典。
    """
    return {"total": total, "items": items}
