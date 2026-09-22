"""Agent 安装包与安装脚本下载接口测试。"""

from __future__ import annotations

import io
import tarfile


def test_download_agent_package(client):
    resp = client.get("/api/v1/agent/package")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/gzip"
    assert "attachment" in resp.headers.get("content-disposition", "")

    data = resp.content
    assert data[:2] == b"\x1f\x8b"  # gzip 魔数

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        names = set(tar.getnames())
    assert "ops-agent/install.sh" in names
    assert "ops-agent/agent/main.py" in names
    assert "ops-agent/agent/config/config.yaml.example" in names
    assert "ops-agent/deploy/systemd/server-agent.service" in names
    assert "ops-agent/VERSION" in names
    # 不应包含 venv/tests/运行时 config
    assert not any(".venv" in n for n in names)
    assert not any("/tests/" in n for n in names)
    assert "ops-agent/agent/config/config.yaml" not in names


def test_get_install_script(client):
    resp = client.get("/api/v1/agent/install.sh")
    assert resp.status_code == 200
    assert "shellscript" in resp.headers["content-type"]
    body = resp.text
    assert "--token" in body
    assert "--code" in body
    assert "systemctl" in body


def test_package_requires_no_auth(client):
    """包与脚本下载无需登录（供目标机 curl 直接获取）。"""
    assert client.get("/api/v1/agent/package").status_code == 200
    assert client.get("/api/v1/agent/install.sh").status_code == 200
