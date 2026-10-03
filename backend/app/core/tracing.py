"""OpenTelemetry 链路追踪配置（后端链路）。

默认关闭（`OTEL_ENABLED=false`）。启用后对 FastAPI / SQLAlchemy / Redis 自动埋点；
配置 `OTEL_EXPORTER_OTLP_ENDPOINT` 时通过 OTLP/HTTP 导出，否则仅生成 span。

`trace_id` 会注入到结构化日志（见 `app/core/logging.py`）。
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

_trace: ModuleType | None
try:  # otel 为运行时可选依赖，缺失时降级
    from opentelemetry import trace as _trace
except Exception:  # pragma: no cover - 依赖缺失时的降级路径
    _trace = None


def current_trace_id() -> str | None:
    """返回当前 span 的 trace_id（32 位十六进制），无有效 span 时返回 None。"""
    if _trace is None:
        return None
    try:
        span_context = _trace.get_current_span().get_span_context()
        if span_context.is_valid:
            return format(span_context.trace_id, "032x")
    except Exception:
        return None
    return None


def setup_tracing(app: Any, engine: Any) -> None:
    """初始化并注册追踪（幂等，配置关闭时直接返回）。"""
    from app.core.config import settings

    if not settings.OTEL_ENABLED:
        return

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/api/v1/health")

    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=engine)

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception:  # pragma: no cover - Redis 埋点失败不影响启动
        pass
