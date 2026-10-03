"""Prometheus 指标接口测试。"""

from __future__ import annotations

from app.core.config import settings
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def test_metrics_endpoint_exposes_gauges(client, db):
    ServerService(db).create_server(
        ServerCreate(server_code="metrics-01", hostname="metrics-01", ip_address="10.9.0.1")
    )

    resp = client.get("/metrics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "ops_agent_status" in body
    assert 'ops_agent_status{status="OFFLINE"} 1.0' in body
    assert "ops_server_total" in body
    assert "ops_alert_active" in body
    assert "ops_task_status" in body


def test_metrics_requires_token_when_configured(client, db):
    original = settings.METRICS_TOKEN
    settings.METRICS_TOKEN = "secret-token"
    try:
        assert client.get("/metrics").status_code == 401
        ok = client.get("/metrics", headers={"Authorization": "Bearer secret-token"})
        assert ok.status_code == 200
    finally:
        settings.METRICS_TOKEN = original


def test_metrics_disabled_returns_404(client, db):
    original = settings.METRICS_ENABLED
    settings.METRICS_ENABLED = False
    try:
        assert client.get("/metrics").status_code == 404
    finally:
        settings.METRICS_ENABLED = original
