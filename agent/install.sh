#!/usr/bin/env bash
#
# ops-monitor Agent 一键安装脚本（systemd）
#
# 用法：
#   sudo ./agent/install.sh [安装目录]
#
# 说明：
#   1. 将 agent 包复制到安装目录（默认 /opt/ops-agent），保持 agent/ 包结构
#   2. 创建虚拟环境并安装依赖
#   3. 准备 config.yaml（优先使用当前目录 ./config.yaml，否则用示例）
#   4. 安装并启动 systemd 服务 server-agent
#
set -euo pipefail

INSTALL_DIR="${1:-/opt/ops-agent}"
SERVICE_NAME="server-agent"
PYTHON_BIN="${PYTHON:-python3.11}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log() { echo -e "\033[32m[install]\033[0m $*"; }
err() { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || err "请使用 root 运行（sudo $0）"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || err "未找到 $PYTHON_BIN，请先安装 Python 3.11+ 或设置 PYTHON 环境变量"

log "安装目录: ${INSTALL_DIR}"
mkdir -p "$INSTALL_DIR"

# 1. 复制 agent 包（保留包结构，保证 python -m agent.main 可用）
log "复制 agent 代码..."
rm -rf "${INSTALL_DIR}/agent"
cp -r "${SCRIPT_DIR}" "${INSTALL_DIR}/agent"
rm -rf "${INSTALL_DIR}/agent/.venv" \
       "${INSTALL_DIR}/agent/tests" \
       "${INSTALL_DIR}/agent/config/config.yaml"
find "${INSTALL_DIR}/agent" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# 2. 虚拟环境与依赖
log "创建虚拟环境并安装依赖..."
[ -d "${INSTALL_DIR}/.venv" ] || "$PYTHON_BIN" -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/pip" install -q --upgrade pip
"${INSTALL_DIR}/.venv/bin/pip" install -q -r "${INSTALL_DIR}/agent/requirements.txt"

# 3. 配置文件
CONFIG_DST="${INSTALL_DIR}/agent/config/config.yaml"
if [ -f "${REPO_ROOT}/config.yaml" ]; then
  log "使用 ${REPO_ROOT}/config.yaml"
  cp "${REPO_ROOT}/config.yaml" "$CONFIG_DST"
elif [ ! -f "$CONFIG_DST" ]; then
  log "生成默认配置（请随后编辑 Token/server_code/url）"
  cp "${INSTALL_DIR}/agent/config/config.yaml.example" "$CONFIG_DST"
fi
chmod 600 "$CONFIG_DST"

# 4. systemd 服务
log "安装 systemd 服务 ${SERVICE_NAME}..."
sed "s#__INSTALL_DIR__#${INSTALL_DIR}#g" \
  "${REPO_ROOT}/deploy/systemd/server-agent.service" \
  > "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"

log "完成。查看状态：systemctl status ${SERVICE_NAME} --no-pager"
log "查看日志：journalctl -u ${SERVICE_NAME} -f"
