#!/usr/bin/env bash
#
# ops-monitor Agent 安装脚本（systemd）
#
# 支持两种运行方式：
#   1) 一键安装（平台向导生成的命令，无需手动配置）
#      curl -fsSL http://<platform>/api/v1/agent/install.sh | sudo bash -s -- \
#        --url http://<platform> --token <TOKEN> --code <SERVER_CODE> [--services nginx,docker,ssh]
#   2) 本地/仓库运行
#      sudo ./agent/install.sh [--config ./config.yaml]
#
# 参数：
#   --url URL         服务端地址
#   --token TOKEN     Agent 注册凭证
#   --code CODE       服务器编码（与平台一致）
#   --services LIST   服务白名单，逗号分隔（默认 nginx,docker,ssh）
#   --dir DIR         安装目录（默认 /opt/ops-agent）
#   --config FILE     使用已有 config.yaml
#
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/ops-agent"
SERVICE_NAME="server-agent"
PYTHON_BIN="${PYTHON:-python3.11}"
URL=""
TOKEN=""
CODE=""
SERVICES=""
CONFIG=""

log() { echo -e "\033[32m[install]\033[0m $*"; }
err() { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
ops-monitor Agent 安装脚本（systemd）

用法：
  # 一键安装（平台向导生成）
  curl -fsSL http://<platform>/api/v1/agent/install.sh | sudo bash -s -- \
    --url http://<platform> --token <TOKEN> --code <SERVER_CODE> [--services nginx,docker,ssh]

  # 本地/仓库运行
  sudo ./agent/install.sh [--config ./config.yaml]

参数：
  --url URL         服务端地址
  --token TOKEN     Agent 注册凭证
  --code CODE       服务器编码（与平台一致）
  --services LIST   服务白名单，逗号分隔（默认 nginx,docker,ssh）
  --dir DIR         安装目录（默认 /opt/ops-agent）
  --config FILE     使用已有 config.yaml
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2:-}"; shift 2 ;;
    --token) TOKEN="${2:-}"; shift 2 ;;
    --code) CODE="${2:-}"; shift 2 ;;
    --services) SERVICES="${2:-}"; shift 2 ;;
    --dir) INSTALL_DIR="${2:-}"; shift 2 ;;
    --config) CONFIG="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) err "未知参数: $1（--help 查看用法）" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || err "请使用 root 运行（sudo）"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || err "未找到 $PYTHON_BIN，请安装 Python 3.11+ 或设置 PYTHON 环境变量"

# 布局检测：包布局（install.sh 与 agent/ 同级）或仓库布局（install.sh 在 agent/ 下）
if [ -d "$SELF_DIR/agent" ]; then
  AGENT_SRC="$SELF_DIR/agent"
  SYSTEMD_SRC="$SELF_DIR/deploy/systemd/server-agent.service"
else
  AGENT_SRC="$SELF_DIR"
  SYSTEMD_SRC="$(cd "$SELF_DIR/.." && pwd)/deploy/systemd/server-agent.service"
fi
[ -d "$AGENT_SRC" ] || err "未找到 agent 包: $AGENT_SRC"
[ -f "$SYSTEMD_SRC" ] || err "未找到 systemd 模板: $SYSTEMD_SRC"

log "安装目录: ${INSTALL_DIR}"
mkdir -p "$INSTALL_DIR"

# 1. 复制 agent 包
log "复制 agent 代码..."
rm -rf "${INSTALL_DIR}/agent"
cp -r "$AGENT_SRC" "${INSTALL_DIR}/agent"
rm -rf "${INSTALL_DIR}/agent/.venv" \
       "${INSTALL_DIR}/agent/tests" \
       "${INSTALL_DIR}/agent/config/config.yaml"
find "${INSTALL_DIR}/agent" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# 2. 虚拟环境与依赖
log "创建虚拟环境并安装依赖..."
[ -d "${INSTALL_DIR}/.venv" ] || "$PYTHON_BIN" -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/pip" install -q --upgrade pip
"${INSTALL_DIR}/.venv/bin/pip" install -q -r "${INSTALL_DIR}/agent/requirements.txt"

# 3. 生成/准备 config.yaml
DEST="${INSTALL_DIR}/agent/config/config.yaml"
mkdir -p "${INSTALL_DIR}/agent/config"
if [ -n "$CONFIG" ]; then
  [ -f "$CONFIG" ] || err "指定的配置文件不存在: $CONFIG"
  log "使用配置: $CONFIG"
  cp "$CONFIG" "$DEST"
elif [ -n "$URL" ] || [ -n "$TOKEN" ] || [ -n "$CODE" ]; then
  [ -n "$URL" ] && [ -n "$TOKEN" ] && [ -n "$CODE" ] || err "一键安装需同时提供 --url、--token、--code"
  [ -z "$SERVICES" ] && SERVICES="nginx,docker,ssh"
  log "根据参数生成配置（server_code=$CODE）"
  {
    echo "server:"
    echo "  url: \"$URL\""
    echo "  token: \"$TOKEN\""
    echo "  server_code: \"$CODE\""
    echo ""
    echo "collect:"
    echo "  heartbeat_interval: 30"
    echo "  metrics_interval: 10"
    echo "  assets_interval: 60"
    echo "  task_poll_interval: 5"
    echo "  retry_max_seconds: 60"
    echo "  connect_timeout: 5"
    echo "  request_timeout: 10"
    echo "  services:"
    IFS=',' read -ra _svc <<< "$SERVICES"
    for s in "${_svc[@]}"; do
      s="$(echo "$s" | xargs)"
      [ -n "$s" ] && echo "    - \"$s\""
    done
    echo ""
    echo "log:"
    echo "  level: \"INFO\""
  } > "$DEST"
elif [ -f "${PWD}/config.yaml" ]; then
  log "使用当前目录 config.yaml"
  cp "${PWD}/config.yaml" "$DEST"
elif [ ! -f "$DEST" ]; then
  log "生成默认配置（请编辑 Token/server_code/url）"
  cp "${INSTALL_DIR}/agent/config/config.yaml.example" "$DEST"
fi
chmod 600 "$DEST"

# 4. systemd 服务
log "安装 systemd 服务 ${SERVICE_NAME}..."
sed "s#__INSTALL_DIR__#${INSTALL_DIR}#g" "$SYSTEMD_SRC" > "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"

log "完成。状态：systemctl status ${SERVICE_NAME} --no-pager"
log "日志：journalctl -u ${SERVICE_NAME} -f"
