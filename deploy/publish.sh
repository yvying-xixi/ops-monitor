#!/usr/bin/env bash
#
# ops-monitor 镜像本地构建并推送到 Harbor（内网 HTTP registry）
#
# 用法：
#   HARBOR_USERNAME=... HARBOR_PASSWORD=... ./deploy/publish.sh [版本号]
#
# 版本号优先级：命令行参数 > 仓库根 VERSION；自动去除前缀 v。
# 会把两个镜像打上 "<版本号>" 与 "latest" 两个 tag 并推送。
#
# 可选环境变量：
#   HARBOR_REGISTRY  默认 192.168.10.24
#   HARBOR_PROJECT   默认 ops-monitor
#   PLATFORM         默认 linux/amd64
#
# 前置条件：
#   - 已将 Harbor 主机加入 /etc/docker/daemon.json 的 insecure-registries 并重启 docker
#   - HARBOR_USERNAME / HARBOR_PASSWORD（或已 docker login）
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"

log() { echo -e "\033[32m[publish]\033[0m $*"; }
warn() { echo -e "\033[33m[warn]\033[0m $*" >&2; }
err() { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

VERSION="${1:-$(cat "$REPO_ROOT/VERSION" 2>/dev/null || true)}"
[ -n "$VERSION" ] || err "未指定版本且未找到 VERSION 文件"
VERSION="${VERSION#v}"

HARBOR_REGISTRY="${HARBOR_REGISTRY:-192.168.10.24}"
HARBOR_PROJECT="${HARBOR_PROJECT:-ops-monitor}"
PLATFORM="${PLATFORM:-linux/amd64}"

command -v docker >/dev/null 2>&1 || err "未安装 docker"
[ -n "${HARBOR_USERNAME:-}" ] || err "缺少 HARBOR_USERNAME"
[ -n "${HARBOR_PASSWORD:-}" ] || err "缺少 HARBOR_PASSWORD"

if docker info 2>/dev/null | grep -A100 'Insecure Registries' | grep -q "$HARBOR_REGISTRY"; then
  log "insecure-registries 已包含 $HARBOR_REGISTRY"
else
  warn "未在 docker insecure-registries 中发现 $HARBOR_REGISTRY"
  warn "请将其加入 /etc/docker/daemon.json 的 insecure-registries 并重启 docker，否则推送 HTTP registry 会失败"
fi

log "登录 $HARBOR_REGISTRY ..."
printf '%s' "$HARBOR_PASSWORD" | docker login "$HARBOR_REGISTRY" -u "$HARBOR_USERNAME" --password-stdin

build_push() {
  local local_tag="$1" repo="$2" context="$3" dockerfile="$4"
  log "构建 $repo（$PLATFORM）..."
  docker build --platform "$PLATFORM" -t "$local_tag" -f "$dockerfile" "$context"
  local tag remote
  for tag in "$VERSION" latest; do
    remote="${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${repo}:${tag}"
    docker tag "$local_tag" "$remote"
    log "推送 $remote ..."
    docker push "$remote"
  done
}

build_push "ops-monitor-backend:local" "ops-monitor-backend" \
  "$REPO_ROOT/backend" "$REPO_ROOT/deploy/docker/Dockerfile.backend"

build_push "ops-monitor-frontend:local" "ops-monitor-frontend" \
  "$REPO_ROOT" "$REPO_ROOT/deploy/nginx/Dockerfile"

log "完成。镜像："
echo "  ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/ops-monitor-backend:${VERSION} 与 :latest"
echo "  ${HARBOR_REGISTRY}/${HARBOR_PROJECT}/ops-monitor-frontend:${VERSION} 与 :latest"
echo "部署：IMAGE_REGISTRY=${HARBOR_REGISTRY}/${HARBOR_PROJECT} IMAGE_TAG=v${VERSION} ./deploy/install.sh"
