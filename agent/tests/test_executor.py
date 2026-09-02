"""Agent 受控执行器测试（mock subprocess）。"""

from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from agent.executor.service import ServiceExecutor


def _fake_run(returncode=0, stdout="ok", stderr="", raise_timeout=False, raise_oserror=False):
    def _inner(*args, **kwargs):
        if raise_timeout:
            raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))
        if raise_oserror:
            raise OSError("no systemctl")
        proc = mock.Mock()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    return _inner


def test_executor_validates_service_whitelist():
    exe = ServiceExecutor(["nginx"])
    with pytest.raises(ValueError):
        exe.run_action("apache2", "START")


def test_executor_validates_action():
    exe = ServiceExecutor(["nginx"])
    with pytest.raises(ValueError):
        exe.run_action("nginx", "SHELL")


def test_status_success():
    exe = ServiceExecutor(["nginx"])
    with mock.patch.object(subprocess, "run", side_effect=_fake_run(returncode=0, stdout="active")):
        success, output = exe.run_action("nginx", "STATUS")
    assert success is True
    assert output == "active"


def test_start_failure():
    exe = ServiceExecutor(["nginx"])
    with mock.patch.object(subprocess, "run", side_effect=_fake_run(returncode=1, stderr="Job failed")):
        success, output = exe.run_action("nginx", "START")
    assert success is False
    assert "failed" in output.lower()


def test_timeout_reports_failure():
    exe = ServiceExecutor(["nginx"])
    with mock.patch.object(subprocess, "run", side_effect=_fake_run(raise_timeout=True)):
        success, output = exe.run_action("nginx", "RESTART", timeout=5)
    assert success is False
    assert "超时" in output


def test_no_shell_invocation():
    """校验命令以参数列表执行，绝无 shell 拼接。"""
    exe = ServiceExecutor(["nginx"])
    with mock.patch.object(subprocess, "run", side_effect=_fake_run()) as mocked:
        exe.run_action("nginx", "RESTART")
    args, kwargs = mocked.call_args
    assert kwargs.get("shell") is not True
    assert args[0] == ["systemctl", "restart", "nginx"]


def test_fetch_logs():
    exe = ServiceExecutor(["nginx"])
    with mock.patch.object(subprocess, "run", side_effect=_fake_run(stdout="log line 1\nlog line 2")):
        success, output = exe.fetch_logs("nginx", lines=10)
    assert success is True
    assert "log line 1" in output
