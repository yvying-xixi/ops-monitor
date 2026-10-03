"""Agent 安装包与安装脚本下载接口测试（支持 python / go 双运行时）。"""

from __future__ import annotations

import io
import tarfile


def test_download_python_agent_package(client):
    resp = client.get("/api/v1/agent/package")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/gzip"
    assert "attachment" in resp.headers.get("content-disposition", "")
    # 默认运行时文件名为 python
    assert "ops-agent-python-" in resp.headers["content-disposition"]

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


def test_download_go_agent_package(client):
    resp = client.get("/api/v1/agent/package?runtime=go")
    assert resp.status_code == 200
    assert "ops-agent-go-" in resp.headers["content-disposition"]

    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
        names = set(tar.getnames())
    assert "ops-agent/install.sh" in names
    assert "ops-agent/deploy/systemd/server-agent-go.service" in names
    assert "ops-agent/VERSION" in names
    # Go 包应包含预编译二进制
    assert any(n.startswith("ops-agent/dist/ops-agent-") for n in names)
    # 不应包含 Python 源码
    assert not any(n.startswith("ops-agent/agent/") for n in names)


def test_unknown_runtime_falls_back_to_python(client):
    resp = client.get("/api/v1/agent/package?runtime=ruby")
    assert resp.status_code == 200
    assert "ops-agent-python-" in resp.headers["content-disposition"]


def test_get_python_install_script(client):
    resp = client.get("/api/v1/agent/install.sh")
    assert resp.status_code == 200
    assert "shellscript" in resp.headers["content-type"]
    body = resp.text
    assert "--token" in body
    assert "--code" in body
    assert "systemctl" in body
    # Python 脚本含 venv 安装
    assert "venv" in body


def test_get_go_install_script(client):
    resp = client.get("/api/v1/agent/install.sh?runtime=go")
    assert resp.status_code == 200
    body = resp.text
    assert "--token" in body
    assert "systemctl" in body
    # Go 脚本部署二进制而非 venv
    assert 'BIN_NAME="ops-agent"' in body
    assert "dist" in body
    assert "uname -m" in body


def test_package_requires_no_auth(client):
    """包与脚本下载无需登录（供目标机 curl 直接获取）。"""
    assert client.get("/api/v1/agent/package").status_code == 200
    assert client.get("/api/v1/agent/install.sh").status_code == 200
    assert client.get("/api/v1/agent/package?runtime=go").status_code == 200
    assert client.get("/api/v1/agent/install.sh?runtime=go").status_code == 200
