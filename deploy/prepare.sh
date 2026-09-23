#!/usr/bin/env bash
#
# 校验 deploy/config.env 并渲染 deploy/.env 与 HTTPS 覆盖配置（不启动容器）
#
# config.env 为 Bash-compatible 配置文件（由 shell source 执行），
# 仅允许受信任的部署管理员编辑。
#
# 用法：
#   ./deploy/prepare.sh            # 校验 + 渲染（空密钥生成并回写 config.env）
#   ./deploy/prepare.sh --check    # 仅校验（只读：不生成密钥、不写任何文件）
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.env}"
ENV_FILE="$DEPLOY_DIR/.env"

log()  { echo -e "\033[32m[prepare]\033[0m $*"; }
warn() { echo -e "\033[33m[warn]\033[0m $*"; }
err()  { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

[ -f "$CONFIG" ] || err "配置文件不存在: $CONFIG（先执行 install.sh 或 cp config.env.tmpl config.env）"

command -v sed >/dev/null 2>&1 || err "缺少 sed"
command -v od  >/dev/null 2>&1 || err "缺少 od"
command -v tr  >/dev/null 2>&1 || err "缺少 tr"

# 载入配置（config.env 为受信任的 Bash 配置文件）
set -a
# shellcheck disable=SC1090
. "$CONFIG"
set +a

# 弱密钥判定：常见弱口令或长度 < 8
is_weak() {
  case "$1" in
    ""|change-me|changeme|password|123456|admin|admin123456) return 0 ;;
  esac
  [ "${#1}" -lt 8 ]
}

validate() {
  local failed=0
  [ -n "${HOSTNAME:-}" ] || { echo "[error] HOSTNAME 不能为空（平台对外访问地址）" >&2; failed=1; }
  case "${HTTP_PORT:-}" in
    ''|*[!0-9]*) echo "[error] HTTP_PORT 必须是 1-65535 的整数" >&2; failed=1 ;;
    *) { [ "$HTTP_PORT" -ge 1 ] && [ "$HTTP_PORT" -le 65535 ]; } || { echo "[error] HTTP_PORT 必须是 1-65535 的整数" >&2; failed=1; } ;;
  esac
  [ -n "${DB_NAME:-}" ] || { echo "[error] DB_NAME 不能为空" >&2; failed=1; }
  [ -n "${DATA_VOLUME_DIR:-}" ] || { echo "[error] DATA_VOLUME_DIR 不能为空" >&2; failed=1; }

  if [ "${HTTPS_ENABLED:-false}" = "true" ]; then
    [ -n "${HTTPS_CERTIFICATE:-}" ] || { echo "[error] HTTPS_ENABLED=true 但未配置 HTTPS_CERTIFICATE" >&2; failed=1; }
    [ -n "${HTTPS_PRIVATE_KEY:-}" ] || { echo "[error] HTTPS_ENABLED=true 但未配置 HTTPS_PRIVATE_KEY" >&2; failed=1; }
    [ -z "${HTTPS_CERTIFICATE:-}" ] || [ -e "$HTTPS_CERTIFICATE" ] || { echo "[error] 证书文件不存在: $HTTPS_CERTIFICATE" >&2; failed=1; }
    [ -z "${HTTPS_PRIVATE_KEY:-}" ] || [ -e "$HTTPS_PRIVATE_KEY" ] || { echo "[error] 私钥文件不存在: $HTTPS_PRIVATE_KEY" >&2; failed=1; }
  fi

  [ -n "${DB_PASSWORD:-}" ] && is_weak "$DB_PASSWORD" && warn "DB_PASSWORD 过弱（建议留空自动生成或 >= 8 位强密码）"
  [ -n "${REDIS_PASSWORD:-}" ] && is_weak "$REDIS_PASSWORD" && warn "REDIS_PASSWORD 过弱（建议留空自动生成或 >= 8 位强密码）"
  case "${SEED_ADMIN_PASSWORD:-}" in
    change-me|changeme|password|123456|admin|admin123456)
      warn "SEED_ADMIN_PASSWORD 使用常见弱口令，上线前请修改" ;;
  esac
  return "$failed"
}

validate || exit 1

if [ "${1:-}" = "--check" ]; then
  log "配置校验通过: $CONFIG"
  exit 0
fi

# --- 以下为写操作（--check 不会到达这里）---

# 生成空密钥并回写 config.env（64 位 hex，shell-safe）
gen_secret() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }

changed=0
for key in DB_PASSWORD REDIS_PASSWORD JWT_SECRET_KEY SEED_ADMIN_PASSWORD; do
  eval "current=\${$key:-}"
  if [ -z "$current" ]; then
    value="$(gen_secret)"
    sed -i "s|^${key}=.*|${key}=\"${value}\"|" "$CONFIG"
    printf -v "$key" '%s' "$value"
    changed=1
  fi
done
[ "$changed" -eq 1 ] && chmod 600 "$CONFIG" && log "已生成缺失的密钥并回写 $CONFIG"

# 解析数据目录为绝对路径并创建子目录
case "${DATA_VOLUME_DIR:-}" in
  /*) : ;;
  *) DATA_VOLUME_DIR="$DEPLOY_DIR/$DATA_VOLUME_DIR" ;;
esac
mkdir -p "$DATA_VOLUME_DIR/mysql" "$DATA_VOLUME_DIR/redis"
DATA_VOLUME_DIR="$(cd "$DATA_VOLUME_DIR" && pwd)"

# 派生镜像与 CORS
registry="${IMAGE_REGISTRY:-}"; registry="${registry%/}"
tag="${IMAGE_TAG:-latest}"; [ -n "$tag" ] || tag="latest"
if [ -n "$registry" ]; then
  backend_image="$registry/ops-monitor-backend:$tag"
  nginx_image="$registry/ops-monitor-nginx:$tag"
else
  backend_image="ops-monitor-backend:local"
  nginx_image="ops-monitor-nginx:local"
fi
if [ "${HTTP_PORT:-80}" = "80" ]; then
  origin="http://${HOSTNAME}"
else
  origin="http://${HOSTNAME}:${HTTP_PORT}"
fi

# 渲染 deploy/.env（Compose 使用；单引号包裹 CORS 以保留 JSON 内层引号）
umask 077
{
  echo "# 本文件由 deploy/prepare.sh 自动生成，请勿手动修改"
  echo "HOSTNAME=${HOSTNAME}"
  echo "HTTP_PORT=${HTTP_PORT}"
  echo "HTTPS_ENABLED=$([ "${HTTPS_ENABLED:-false}" = "true" ] && echo true || echo false)"
  echo "HTTPS_PORT=${HTTPS_PORT:-443}"
  echo "HTTPS_CERTIFICATE=${HTTPS_CERTIFICATE:-}"
  echo "HTTPS_PRIVATE_KEY=${HTTPS_PRIVATE_KEY:-}"
  echo "DB_NAME=${DB_NAME:-ops_monitor}"
  echo "DB_PASSWORD=${DB_PASSWORD:-}"
  echo "REDIS_PASSWORD=${REDIS_PASSWORD:-}"
  echo "JWT_SECRET_KEY=${JWT_SECRET_KEY:-}"
  echo "JWT_EXPIRE_MINUTES=${JWT_EXPIRE_MINUTES:-120}"
  echo "SEED_ADMIN_USERNAME=${SEED_ADMIN_USERNAME:-admin}"
  echo "SEED_ADMIN_PASSWORD=${SEED_ADMIN_PASSWORD:-}"
  echo "SEED_INIT_DATA=${SEED_INIT_DATA:-true}"
  echo "METRIC_RETENTION_DAYS=${METRIC_RETENTION_DAYS:-7}"
  echo "OPERATION_LOG_ENABLED=${OPERATION_LOG_ENABLED:-true}"
  echo "CORS_ORIGINS='[\"${origin}\"]'"
  echo "DATA_VOLUME_DIR=${DATA_VOLUME_DIR}"
  echo "IMAGE_REGISTRY=${registry}"
  echo "IMAGE_TAG=${tag}"
  echo "BACKEND_IMAGE=${backend_image}"
  echo "NGINX_IMAGE=${nginx_image}"
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

# 载入渲染结果用于 HTTPS 处理
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

mkdir -p "$DEPLOY_DIR/nginx/certs" "$DEPLOY_DIR/nginx/conf.d"

if [ "${HTTPS_ENABLED:-false}" = "true" ]; then
  [ -n "${HTTPS_CERTIFICATE:-}" ] && [ -n "${HTTPS_PRIVATE_KEY:-}" ] || err "HTTPS 已启用但证书/私钥路径为空"
  cp -f "$HTTPS_CERTIFICATE" "$DEPLOY_DIR/nginx/certs/fullchain.pem"
  cp -f "$HTTPS_PRIVATE_KEY" "$DEPLOY_DIR/nginx/certs/privkey.pem"
  chmod 600 "$DEPLOY_DIR/nginx/certs/privkey.pem" || true

  cat > "$DEPLOY_DIR/nginx/conf.d/https.conf" <<'NGINX'
server {
    listen 443 ssl;
    server_name _;
    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINX

  cat > "$DEPLOY_DIR/docker/compose.https.yml" <<EOF
services:
  nginx:
    ports:
      - "${HTTPS_PORT:-443}:443"
EOF
  log "HTTPS 已启用（443 端口映射 + 证书就位）"
else
  rm -f "$DEPLOY_DIR/nginx/conf.d/https.conf" "$DEPLOY_DIR/docker/compose.https.yml"
fi

log "完成：$ENV_FILE"
