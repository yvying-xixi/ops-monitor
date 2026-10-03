#!/usr/bin/env bash
#
# 运行 Ops Monitor 负载测试（Locust headless）。
#
# 用法：
#   BASE_URL=http://127.0.0.1:8000 USERS=50 SPAWN_RATE=5 RUN_TIME=60s ./benchmarks/run.sh
#
# 环境变量：
#   BASE_URL    被测平台地址（默认 http://127.0.0.1:8000）
#   USERS       并发用户数（默认 50）
#   SPAWN_RATE  每秒启动用户数（默认 5）
#   RUN_TIME    运行时长（默认 60s）
#   OPS_USERNAME / OPS_PASSWORD / OPS_ENABLE_WRITE / OPS_SERVER_ID  见 locustfile.py
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${BASE_URL:-http://127.0.0.1:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-5}"
RUN_TIME="${RUN_TIME:-60s}"

echo "[bench] host=${HOST} users=${USERS} spawn=${SPAWN_RATE} run=${RUN_TIME}"
exec locust -f "${SCRIPT_DIR}/locustfile.py" --headless \
  -H "${HOST}" -u "${USERS}" -r "${SPAWN_RATE}" -t "${RUN_TIME}" "$@"
