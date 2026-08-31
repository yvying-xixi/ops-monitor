"""Agent 配置加载测试。"""

from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

from agent.config.config import load_config


def _write_config(tmp_path, content: str):
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(path)


def test_load_config(tmp_path):
    path = _write_config(
        tmp_path,
        """
        server:
          url: "http://127.0.0.1:8000"
          token: "test-token"
          server_code: "web-01"
        collect:
          heartbeat_interval: 30
          metrics_interval: 10
        log:
          level: "DEBUG"
        """,
    )
    config = load_config(path)
    assert config.server.url == "http://127.0.0.1:8000"
    assert config.server.token == "test-token"
    assert config.server.server_code == "web-01"
    assert config.collect.heartbeat_interval == 30
    assert config.collect.metrics_interval == 10
    assert config.log.level == "DEBUG"
    # 未指定的字段使用默认值
    assert config.collect.assets_interval == 60
    assert config.collect.retry_max_seconds == 60


def test_load_config_requires_token(tmp_path):
    path = _write_config(
        tmp_path,
        """
        server:
          url: "http://127.0.0.1:8000"
          token: ""
          server_code: "web-01"
        """,
    )
    with pytest.raises(ValidationError):
        load_config(path)
