"""服务器只读发现接口测试（白名单 CIDR + 探测）。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import discovery_service


@pytest.fixture()
def discovery_on():
    original = (
        settings.DISCOVERY_ENABLED,
        settings.DISCOVERY_ALLOWED_CIDRS,
        settings.DISCOVERY_MAX_HOSTS,
    )
    settings.DISCOVERY_ENABLED = True
    settings.DISCOVERY_ALLOWED_CIDRS = ["10.0.0.0/24"]
    settings.DISCOVERY_MAX_HOSTS = 256
    try:
        yield
    finally:
        (
            settings.DISCOVERY_ENABLED,
            settings.DISCOVERY_ALLOWED_CIDRS,
            settings.DISCOVERY_MAX_HOSTS,
        ) = original


@pytest.fixture()
def fake_probe(monkeypatch):
    def probe(ip: str, port: int, timeout: float):
        if ip == "10.0.0.5":
            return True, "SSH-2.0-OpenSSH_9.0"
        return False, None

    monkeypatch.setattr(discovery_service, "_probe", probe)


def test_discovery_disabled_returns_403(client, admin_headers):
    resp = client.post(
        "/api/v1/discovery/scan", json={"cidr": "10.0.0.0/30"}, headers=admin_headers
    )
    assert resp.status_code == 403


def test_scan_rejects_cidr_outside_allowlist(client, admin_headers, discovery_on, fake_probe):
    resp = client.post(
        "/api/v1/discovery/scan", json={"cidr": "192.168.1.0/24"}, headers=admin_headers
    )
    assert resp.status_code == 403


def test_scan_rejects_invalid_cidr(client, admin_headers, discovery_on, fake_probe):
    resp = client.post(
        "/api/v1/discovery/scan", json={"cidr": "not-a-cidr"}, headers=admin_headers
    )
    assert resp.status_code == 400


def test_scan_rejects_too_many_hosts(client, admin_headers, discovery_on, fake_probe):
    original = settings.DISCOVERY_MAX_HOSTS
    settings.DISCOVERY_MAX_HOSTS = 4
    try:
        resp = client.post(
            "/api/v1/discovery/scan", json={"cidr": "10.0.0.0/24"}, headers=admin_headers
        )
        assert resp.status_code == 400
    finally:
        settings.DISCOVERY_MAX_HOSTS = original


def test_scan_returns_open_hosts(client, admin_headers, discovery_on, fake_probe):
    resp = client.post(
        "/api/v1/discovery/scan", json={"cidr": "10.0.0.4/30"}, headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["count"] == 1
    assert data["hosts"][0]["ip"] == "10.0.0.5"
    assert "SSH-2.0" in data["hosts"][0]["banner"]


def test_discovery_config(client, admin_headers, discovery_on):
    resp = client.get("/api/v1/discovery/config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["enabled"] is True
    assert data["allowed_cidrs"] == ["10.0.0.0/24"]
