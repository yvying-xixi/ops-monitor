"""零依赖只读负载 smoke：用标准库对热点接口施压并输出延迟分位。

用于快速建立/复核基线与在无 Locust 环境自检；完整压测建议使用
`benchmarks/locustfile.py`（Locust）。

用法：
    BASE_URL=http://127.0.0.1:8000 USERS=20 DURATION=15 \
        OPS_USERNAME=admin OPS_PASSWORD=admin123456 \
        python benchmarks/smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USERS = int(os.getenv("USERS", "20"))
DURATION = float(os.getenv("DURATION", "15"))
USERNAME = os.getenv("OPS_USERNAME", "admin")
PASSWORD = os.getenv("OPS_PASSWORD", "admin123456")

_lock = threading.Lock()
_stats: dict[str, list[float]] = {}
_status: dict[str, dict[int, int]] = {}


def _record(path: str, latency_ms: float, code: int) -> None:
    with _lock:
        _stats.setdefault(path, []).append(latency_ms)
        _status.setdefault(path, {})
        _status[path][code] = _status[path].get(code, 0) + 1


def _request(method: str, url: str, token: str | None = None, body: dict | None = None) -> tuple[float, int]:
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return (time.perf_counter() - start) * 1000, resp.status
    except urllib.error.HTTPError as exc:
        return (time.perf_counter() - start) * 1000, exc.code
    except Exception:
        return (time.perf_counter() - start) * 1000, 0


def _login() -> str:
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/login",
        data=json.dumps({"username": USERNAME, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"登录失败: HTTP {exc.code}") from exc
    return payload["data"]["access_token"]


def _server_id(token: str) -> int | None:
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/servers?page=1&page_size=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        items = json.load(resp).get("data", {}).get("items", [])
    return items[0]["id"] if items else None


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    floor = int(k)
    ceil = min(floor + 1, len(ordered) - 1)
    return ordered[floor] + (ordered[ceil] - ordered[floor]) * (k - floor)


def _worker(endpoints: list[str], token: str, deadline: float) -> None:
    idx = 0
    while time.perf_counter() < deadline:
        path = endpoints[idx % len(endpoints)]
        idx += 1
        latency, code = _request("GET", f"{BASE_URL}{path}", token=token)
        _record(path, latency, code)


def main() -> None:
    token = _login()
    sid = _server_id(token)
    if sid is None:
        print("[warn] 无服务器数据，跳过指标类接口", file=sys.stderr)

    endpoints = [
        "/api/v1/dashboard/overview",
        "/api/v1/servers?page=1&page_size=20",
        "/api/v1/alerts?page=1&page_size=20",
        "/api/v1/alerts/rules",
        "/api/v1/tasks?page=1&page_size=20",
    ]
    if sid:
        endpoints += [
            f"/api/v1/servers/{sid}",
            f"/api/v1/monitor/{sid}/metrics/latest",
            f"/api/v1/monitor/{sid}/metrics/summary?range=1h",
        ]

    print(f"[smoke] {BASE_URL} users={USERS} duration={DURATION}s endpoints={len(endpoints)}")
    deadline = time.perf_counter() + DURATION
    with ThreadPoolExecutor(max_workers=USERS) as pool:
        for _ in range(USERS):
            pool.submit(_worker, endpoints, token, deadline)

    all_latencies: list[float] = []
    total = 0
    failures = 0
    rows = []
    for path, latencies in sorted(_stats.items()):
        codes = _status.get(path, {})
        fails = sum(count for code, count in codes.items() if code == 0 or code >= 500)
        total += len(latencies)
        failures += fails
        all_latencies += latencies
        rows.append(
            (path, len(latencies), _percentile(latencies, 0.5), _percentile(latencies, 0.95),
             _percentile(latencies, 0.99), fails)
        )

    print("\n| 接口 | 请求数 | P50(ms) | P95(ms) | P99(ms) | 失败 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for path, count, p50, p95, p99, fails in rows:
        print(f"| `{path}` | {count} | {p50:.1f} | {p95:.1f} | {p99:.1f} | {fails} |")
    rps = total / DURATION if DURATION else 0
    print(
        f"\n总体：请求 {total}，RPS {rps:.1f}，"
        f"P50 {_percentile(all_latencies, 0.5):.1f}ms，"
        f"P95 {_percentile(all_latencies, 0.95):.1f}ms，"
        f"P99 {_percentile(all_latencies, 0.99):.1f}ms，"
        f"失败 {failures}"
    )


if __name__ == "__main__":
    main()
