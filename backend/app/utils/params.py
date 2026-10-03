"""通用查询参数解析工具。"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator


def optional_int(min_value: int | None = None, max_value: int | None = None):
    """构造可选整型查询参数类型。

    前端清空过滤条件时可能发送 `key=`（空串），此处将空串按未传处理，
    并对非空值做整数解析与范围校验。

    用法：`status: optional_int(0, 1) = None`

    Note:
        需使用裸默认值 `= None`，不要再叠加 `Query(ge=..., le=...)`，
        否则 FastAPI 会丢弃这里的 BeforeValidator。
    """

    def _validate(value: object) -> int | None:
        if isinstance(value, str) and value == "":
            value = None
        if value is None:
            return None
        if not isinstance(value, int | float | str):
            raise ValueError("Input should be a valid integer")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError("Input should be a valid integer") from None
        if min_value is not None and parsed < min_value:
            raise ValueError(f"Input should be greater than or equal to {min_value}")
        if max_value is not None and parsed > max_value:
            raise ValueError(f"Input should be less than or equal to {max_value}")
        return parsed

    return Annotated[int | None, BeforeValidator(_validate)]
