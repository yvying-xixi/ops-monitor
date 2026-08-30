"""统一业务异常。"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """业务异常，携带错误码与 HTTP 状态码，由全局异常处理器统一输出。

    Attributes:
        code: 业务错误码，见 `exceptions.error_codes.ErrorCode`。
        message: 错误描述。
        http_status: 对应 HTTP 状态码。
        data: 附加错误数据，可选。
    """

    def __init__(
        self,
        code: int,
        message: str,
        http_status: int = 400,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data
