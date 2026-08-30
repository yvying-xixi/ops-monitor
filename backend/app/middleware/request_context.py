"""请求上下文中间件：生成/透传 X-Request-ID，并 best-effort 解析当前用户。"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_access_token


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为请求注入 `request_id` 与当前用户 ID。

    请求进入时：
    - 从 `X-Request-ID` 头透传或生成新的 request_id，写入 `request.state.request_id`。
    - 尝试解析 `Authorization: Bearer` 中的 JWT，将用户 ID 写入 `request.state.user_id`
      （解析失败仅置空，不阻断请求）。
    响应返回时在响应头回写 `X-Request-ID`。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        user_id = None
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :]
            try:
                user_id = decode_access_token(token)
            except Exception:
                user_id = None
        request.state.user_id = user_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
