"""统一业务错误码定义。"""

from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    """业务错误码。

    0 表示成功；400/401/403/404/409/500 为通用错误；
    业务细分错误码使用 HTTP 状态码前缀 + 两位序号。
    """

    OK = 0

    BAD_REQUEST = 40000
    UNAUTHORIZED = 40100
    INVALID_CREDENTIALS = 40101
    ACCOUNT_DISABLED = 40102
    FORBIDDEN = 40300
    USER_NOT_FOUND = 40401
    ROLE_NOT_FOUND = 40402
    USERNAME_EXISTS = 40901
    EMAIL_EXISTS = 40902
    INTERNAL_ERROR = 50000
