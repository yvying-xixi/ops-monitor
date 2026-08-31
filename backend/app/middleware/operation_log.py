"""操作审计中间件：将受保护接口的请求记录到 `sys_operation_log`。"""

from __future__ import annotations

import logging
import time

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import SysOperationLog, SysUser
from app.utils.request import get_client_ip

logger = logging.getLogger(__name__)

EXCLUDE_PATHS = {
    "/api/v1/health",
    "/api/v1/auth/login",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class OperationLogMiddleware(BaseHTTPMiddleware):
    """操作审计中间件。

    对 `/api/v1` 下非白名单接口，在请求完成后记录操作日志：
    用户、模块、操作、方法、路径、IP、请求 ID、结果状态、耗时。
    使用独立 `SessionLocal` 写入并 `try/except` 兜底，异常不阻断业务请求。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if (
            not settings.OPERATION_LOG_ENABLED
            or not path.startswith("/api/v1")
            or path.startswith("/api/v1/agent/")
            or path in EXCLUDE_PATHS
        ):
            return await call_next(request)

        start = time.perf_counter()
        error_message = None
        try:
            response = await call_next(request)
        except Exception as exc:
            response = None
            error_message = str(exc)
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            status = response.status_code if response is not None else 500
            self._write_log(
                request=request,
                request_id=getattr(request.state, "request_id", None),
                user_id=getattr(request.state, "user_id", None),
                http_status=status,
                duration_ms=duration_ms,
                error_message=error_message,
            )
        return response

    def _write_log(
        self,
        *,
        request: Request,
        request_id: str | None,
        user_id: int | None,
        http_status: int,
        duration_ms: int,
        error_message: str | None,
    ) -> None:
        """写入操作日志（独立事务，best-effort）。"""
        db = SessionLocal()
        try:
            username = None
            if user_id is not None:
                username = db.scalar(
                    select(SysUser.username).where(SysUser.id == user_id)
                )
            query_params = dict(request.query_params) if request.query_params else None
            log = SysOperationLog(
                user_id=user_id,
                username=username,
                module=self._guess_module(request.url.path),
                operation=f"{request.method} {self._guess_resource(request.url.path)}",
                http_method=request.method,
                request_path=request.url.path,
                request_ip=get_client_ip(request),
                request_id=request_id,
                request_params=query_params,
                result_status="FAILED" if (http_status >= 400 or error_message) else "SUCCESS",
                error_message=error_message,
                duration_ms=duration_ms,
            )
            db.add(log)
            db.commit()
        except Exception:
            logger.exception("操作日志写入失败: %s %s", request.method, request.url.path)
        finally:
            db.close()

    @staticmethod
    def _guess_module(path: str) -> str:
        parts = path.strip("/").split("/")
        return parts[2] if len(parts) >= 3 else path

    @staticmethod
    def _guess_resource(path: str) -> str:
        parts = path.strip("/").split("/")
        return parts[3] if len(parts) >= 4 else (parts[2] if len(parts) >= 3 else path)
