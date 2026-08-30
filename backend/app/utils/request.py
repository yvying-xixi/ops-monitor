"""请求工具函数。"""

from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """从请求中提取客户端 IP。

    优先取 `X-Forwarded-For` 首段（存在代理时），否则回退到直连地址。

    Args:
        request: FastAPI 请求对象。

    Returns:
        客户端 IP 字符串，无法获取时返回 None。
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
