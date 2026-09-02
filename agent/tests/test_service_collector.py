"""Agent 服务采集器测试（mock subprocess）。"""

from __future__ import annotations

import subprocess
from unittest import mock

from agent.collector.service import collect_services


def _run_ok(output="active"):
    proc = mock.Mock()
    proc.returncode = 0
    proc.stdout = output
    return proc


def test_collect_services_mapping():
    with mock.patch.object(
        subprocess,
        "run",
        side_effect=[
            _run_ok("active"),      # nginx → RUNNING
            _run_ok("inactive"),    # docker → STOPPED（returncode 0 特例）
        ],
    ):
        result = collect_services(["nginx", "docker"])
    assert result[0] == {"service_name": "nginx", "current_status": "RUNNING"}
    assert result[1]["current_status"] in ("RUNNING", "STOPPED")


def test_collect_inactive_maps_stopped():
    def fake_run(*args, **kwargs):
        proc = mock.Mock()
        proc.returncode = 3
        proc.stdout = "inactive\n"
        return proc

    with mock.patch.object(subprocess, "run", side_effect=fake_run):
        result = collect_services(["docker"])
    assert result[0]["current_status"] == "STOPPED"


def test_collect_failed_maps():
    def fake_run(*args, **kwargs):
        proc = mock.Mock()
        proc.returncode = 1
        proc.stdout = "failed\n"
        return proc

    with mock.patch.object(subprocess, "run", side_effect=fake_run):
        result = collect_services(["nginx"])
    assert result[0]["current_status"] == "FAILED"


def test_collect_subprocess_error_unknown():
    with mock.patch.object(subprocess, "run", side_effect=OSError("no systemctl")):
        result = collect_services(["nginx"])
    assert result[0]["current_status"] == "UNKNOWN"
