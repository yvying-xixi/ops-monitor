"""Prometheus 指标接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.metrics import refresh_gauges, render_latest

router = APIRouter(tags=["监控指标"])

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/metrics", summary="Prometheus 指标", include_in_schema=False)
def metrics(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Response:
    """暴露平台自有指标，供 Prometheus 抓取。

    默认仅在内网可达（backend 端口未对外暴露）。设置 `METRICS_TOKEN` 后需携带
    `Authorization: Bearer <token>`。`METRICS_ENABLED=false` 时返回 404。
    """
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")
    if settings.METRICS_TOKEN and authorization != f"Bearer {settings.METRICS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    refresh_gauges(db)
    return Response(content=render_latest(), media_type=PROMETHEUS_CONTENT_TYPE)
