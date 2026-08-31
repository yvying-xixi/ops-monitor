"""Agent 采集器单元测试（真实 psutil 数据，断言合理范围）。"""

from __future__ import annotations

from agent.collector import cpu, disk, memory, network, system


def test_cpu_collect():
    info = cpu.collect()
    assert 0 <= info.usage_percent <= 100
    assert info.cores > 0
    assert info.model is None or isinstance(info.model, str)


def test_memory_collect():
    info = memory.collect()
    assert info.total_bytes > 0
    assert info.used_bytes > 0
    assert 0 <= info.usage_percent <= 100


def test_disk_collect():
    usage = disk.collect_usage_percent()
    assert 0 <= usage <= 100
    assets = disk.collect_assets()
    assert len(assets) >= 1
    assert assets[0].device_name
    assert assets[0].mount_point


def test_network_collect():
    info = network.collect_counts()
    assert info.bytes_sent >= 0
    assert info.bytes_recv >= 0
    assets = network.collect_assets()
    assert all(a.interface_name for a in assets)


def test_system_collect():
    info = system.collect()
    assert info.uptime_seconds > 0
    assert info.tcp_connections >= 0
    assert info.hostname
    assert info.kernel_version


def test_collect_metrics_aggregate():
    from agent.collector import collect_metrics

    metrics = collect_metrics()
    for key in (
        "cpu_usage",
        "memory_usage",
        "memory_used_bytes",
        "disk_usage",
        "network_in_bytes",
        "network_out_bytes",
        "load_1m",
        "load_5m",
        "load_15m",
        "tcp_connections",
        "uptime_seconds",
    ):
        assert key in metrics, f"缺少指标字段 {key}"


def test_collect_system_info_aggregate():
    from agent.collector import collect_system_info

    info = collect_system_info()
    assert info["hostname"]
    assert info["memory_total_bytes"] > 0
    assert info["cpu_cores"] > 0
