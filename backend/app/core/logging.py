"""结构化日志配置：JSON 输出并自动注入请求上下文。

字段约定：timestamp / level / service / logger / request_id / trace_id /
user_id / agent_id / action / message / error。

`request_id` / `user_id` / `trace_id` 通过 `contextvars` 传递，由
`RequestContextMiddleware` 在请求开始时写入，日志 formatter 在输出时读取。
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

SERVICE_NAME = "backend"

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[int | None] = ContextVar("user_id", default=None)
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)

# 允许通过 logger 的 extra 传入、直接落为顶层字段的键
_EXTRA_FIELDS = ("agent_id", "action")


class JsonFormatter(logging.Formatter):
    """将日志记录格式化为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "request_id": request_id_ctx.get(),
            "trace_id": trace_id_ctx.get(),
            "user_id": user_id_ctx.get(),
            "message": record.getMessage(),
        }
        for key in _EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """配置根日志器输出 JSON。

    Args:
        level: 日志级别名称（DEBUG/INFO/WARNING/ERROR）。
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # 交由根日志器统一输出，避免 uvicorn 默认 handler 产生重复/非 JSON 日志
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
