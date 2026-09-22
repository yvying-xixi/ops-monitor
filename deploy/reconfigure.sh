#!/usr/bin/env bash
#
# 修改 deploy/config.yml 后：体检 → 重新渲染 → 重建/重启（数据保留）
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.yml}"
ENV_FILE="$DEPLOY_DIR/.env"

log() { echo -e "\033[32m[reconfigure]\033[0m $*"; }
err() { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

[ -f "$CONFIG" ] || err "配置文件不存在: $CONFIG（先执行 install.sh）"

log "体检配置与环境..."
"$DEPLOY_DIR/check.sh" || err "体检未通过，已中止（请修正后重试）"

log "重新渲染 $ENV_FILE..."
"$DEPLOY_DIR/prepare.sh"

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$REPO_ROOT/docker-compose.yml")
if [ "${HTTPS_ENABLED:-false}" = "true" ]; then
  COMPOSE+=(-f "$DEPLOY_DIR/docker-compose.https.yml")
fi

log "应用变更（重建受影响服务，数据卷保留）..."
"${COMPOSE[@]}" up -d --build

echo
log "重配置完成 ✅  访问地址: http://${HOSTNAME}${HTTP_PORT:+:$HTTP_PORT}"
