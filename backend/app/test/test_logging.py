"""结构化日志格式测试。"""

from __future__ import annotations

import json
import logging

from app.core.logging import JsonFormatter, request_id_ctx, user_id_ctx


def _make_record(message: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=None,
        exc_info=None,
    )


def test_json_formatter_includes_context():
    token_request = request_id_ctx.set("req-123")
    token_user = user_id_ctx.set(42)
    try:
        payload = json.loads(JsonFormatter().format(_make_record("hello world")))
    finally:
        request_id_ctx.reset(token_request)
        user_id_ctx.reset(token_user)

    assert payload["message"] == "hello world"
    assert payload["request_id"] == "req-123"
    assert payload["user_id"] == 42
    assert payload["service"] == "backend"
    assert payload["level"] == "INFO"
    assert "timestamp" in payload


def test_json_formatter_includes_extra_fields():
    record = _make_record("dispatch")
    record.agent_id = "agent-001"
    record.action = "task.dispatch"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["agent_id"] == "agent-001"
    assert payload["action"] == "task.dispatch"


def test_json_formatter_nullable_context():
    payload = json.loads(JsonFormatter().format(_make_record()))

    assert payload["request_id"] is None
    assert payload["user_id"] is None
    assert payload["trace_id"] is None
