#!/usr/bin/env bash
#
# ops-monitor 平台安装脚本（配置化，参考 Harbor install.sh）
#
# 用法：
#   cp deploy/config.env.tmpl deploy/config.env   # 可选：先编辑
#   ./deploy/install.sh
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.env}"
ENV_FILE="$DEPLOY_DIR/.env"

log() { echo -e "\033[32m[install]\033[0m $*"; }
err() { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

# 1. 前置检查（仅需 docker / docker compose / curl / bash 及基础命令）
command -v docker >/dev/null 2>&1 || err "未安装 docker"
docker compose version >/dev/null 2>&1 || err "docker compose v2 不可用"
command -v curl >/dev/null 2>&1 || err "未安装 curl"
for tool in sed od tr; do
  command -v "$tool" >/dev/null 2>&1 || err "缺少 $tool"
done

# 2. 配置：不存在则从模板生成
if [ ! -f "$CONFIG" ]; then
  cp "$DEPLOY_DIR/config.env.tmpl" "$CONFIG"
  chmod 600 "$CONFIG"
  log "已生成默认配置 $CONFIG（HOSTNAME=127.0.0.1）"
  log "如需外部访问，请编辑 HOSTNAME/HTTP_PORT 后重新运行本脚本"
fi

# 3. 渲染 .env（并回写自动生成的密钥）
"$DEPLOY_DIR/prepare.sh"

# 4. 载入渲染结果
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$REPO_ROOT/deploy/docker/compose.yml")
if [ "${HTTPS_ENABLED:-false}" = "true" ]; then
  COMPOSE+=(-f "$DEPLOY_DIR/docker/compose.https.yml")
fi

# 5. 拉取或构建
if [ -n "${IMAGE_REGISTRY:-}" ]; then
  log "从 registry 拉取镜像..."
  "${COMPOSE[@]}" pull
  "${COMPOSE[@]}" up -d
else
  log "本地构建并启动..."
  "${COMPOSE[@]}" up -d --build
fi

# 6. 等待就绪
log "等待服务就绪..."
READY=0
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT}/api/v1/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done

echo
if [ "$READY" -eq 1 ]; then
  log "平台已就绪 ✅"
else
  echo -e "\033[33m[warn]\033[0m 健康检查超时，请查看日志：${COMPOSE[*]} logs -f backend"
fi
if [ "${HTTP_PORT}" = "80" ]; then ACCESS="http://${HOSTNAME}"; else ACCESS="http://${HOSTNAME}:${HTTP_PORT}"; fi
echo "  访问地址 : ${ACCESS}"
echo "  管理员   : ${SEED_ADMIN_USERNAME} / ${SEED_ADMIN_PASSWORD}"
echo "  配置源   : $CONFIG（修改后执行 ./deploy/reconfigure.sh）"
echo "  停止     : ${COMPOSE[*]} down"
