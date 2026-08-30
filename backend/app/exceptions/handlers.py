"""全局异常处理器：将各类异常统一转换为 `{code, message, data}` 响应。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions.app_exception import AppException
from app.exceptions.error_codes import ErrorCode

logger = logging.getLogger(__name__)

_HTTP_STATUS_TO_CODE = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    500: ErrorCode.INTERNAL_ERROR,
}


def _build_body(code: int, message: str, data=None) -> dict:
    return {"code": code, "message": message, "data": data}


def register_exception_handlers(app: FastAPI) -> None:
    """向 FastAPI 应用注册统一异常处理器。

    Args:
        app: FastAPI 应用实例。
    """

    @app.exception_handler(AppException)
    async def _handle_app_exception(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.http_status,
            content=_build_body(exc.code, exc.message, exc.data),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        message = f"参数校验失败: {field} {first.get('msg', '')}".strip()
        return JSONResponse(
            status_code=400,
            content=_build_body(ErrorCode.BAD_REQUEST, message, errors),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException):
        code = _HTTP_STATUS_TO_CODE.get(exc.status_code, ErrorCode.BAD_REQUEST)
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_body(code, str(exc.detail)),
            headers=headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def _handle_db_error(request: Request, exc: SQLAlchemyError):
        logger.exception("数据库异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_build_body(ErrorCode.INTERNAL_ERROR, "服务器内部错误"),
        )

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception):
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_build_body(ErrorCode.INTERNAL_ERROR, "服务器内部错误"),
        )
