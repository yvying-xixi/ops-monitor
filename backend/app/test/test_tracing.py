"""OpenTelemetry 追踪与日志 trace_id 注入测试。"""

from __future__ import annotations

import json
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.core.config import settings
from app.core.logging import JsonFormatter
from app.core.tracing import current_trace_id, setup_tracing


def _ensure_provider() -> trace.Tracer:
    # set_tracer_provider 每进程仅生效一次，重复调用会被忽略
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(TracerProvider())
    return trace.get_tracer("test")


def _make_record() -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 1, "msg", None, None)


def test_current_trace_id_none_without_span():
    assert current_trace_id() is None


def test_current_trace_id_within_span():
    tracer = _ensure_provider()
    with tracer.start_as_current_span("op"):
        trace_id = current_trace_id()
    assert trace_id is not None
    assert len(trace_id) == 32


def test_json_formatter_injects_trace_id():
    tracer = _ensure_provider()
    with tracer.start_as_current_span("op"):
        payload = json.loads(JsonFormatter().format(_make_record()))
    assert payload["trace_id"] is not None


def test_setup_tracing_disabled_is_noop():
    original = settings.OTEL_ENABLED
    settings.OTEL_ENABLED = False
    try:
        setup_tracing(None, None)
    finally:
        settings.OTEL_ENABLED = original
