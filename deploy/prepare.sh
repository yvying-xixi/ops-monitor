#!/usr/bin/env bash
#
# 渲染 deploy/.env 与 HTTPS 覆盖配置（不启动容器）
#
# 用法：
#   ./deploy/prepare.sh                 # 校验 + 渲染
#   ./deploy/prepare.sh --check         # 仅校验
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.yml}"
ENV_FILE="$DEPLOY_DIR/.env"

log() { echo -e "\033[32m[prepare]\033[0m $*"; }
err() { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || err "需要 python3"
python3 -c "import yaml" >/dev/null 2>&1 || err "缺少 PyYAML：apt install -y python3-yaml 或 pip install pyyaml"

if [ "${1:-}" = "--check" ]; then
  exec python3 "$DEPLOY_DIR/prepare.py" --check "$CONFIG"
fi

[ -f "$CONFIG" ] || err "配置文件不存在: $CONFIG（先执行 install.sh 或 cp config.yml.tmpl config.yml）"

python3 "$DEPLOY_DIR/prepare.py" "$CONFIG" "$ENV_FILE"

# 载入渲染结果
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
