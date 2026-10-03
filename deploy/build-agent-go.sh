#!/usr/bin/env bash
#
# 构建 Go Agent 二进制到 agent-go/dist/（供后端打包下载与 compose 挂载）
#
# 优先使用宿主 go（若无则用 golang 容器），产出 linux/amd64 与 linux/arm64。
#
# 用法：
#   ./deploy/build-agent-go.sh                 # 需要时构建（已存在则跳过）
#   FORCE=1 ./deploy/build-agent-go.sh         # 强制重建
#   PLATFORMS="linux/amd64" ./deploy/build-agent-go.sh
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
AGENT_DIR="$REPO_ROOT/agent-go"
DIST_DIR="$AGENT_DIR/dist"
PLATFORMS="${PLATFORMS:-linux/amd64 linux/arm64}"
FORCE="${FORCE:-0}"

log() { echo -e "\033[32m[agent-go]\033[0m $*"; }

[ -d "$AGENT_DIR" ] || { echo "[error] 未找到 agent-go 目录: $AGENT_DIR" >&2; exit 1; }

# 判断 dist 是否已是最新
need_build=0
if [ "$FORCE" = "1" ]; then
  need_build=1
elif [ ! -d "$DIST_DIR" ]; then
  need_build=1
else
  for platform in $PLATFORMS; do
    arch="${platform##*/}"
    [ -f "$DIST_DIR/ops-agent-${platform%%/*}-${arch}" ] || need_build=1
  done
fi

if [ "$need_build" -eq 0 ]; then
  log "二进制已存在，跳过（FORCE=1 可强制重建）"
  exit 0
fi

if command -v go >/dev/null 2>&1; then
  log "使用宿主 go 构建..."
  VERSION="$(cat "$AGENT_DIR/VERSION" 2>/dev/null || echo 0.0.0)" PLATFORMS="$PLATFORMS" "$AGENT_DIR/scripts/build.sh"
else
  command -v docker >/dev/null 2>&1 || { echo "[error] 无宿主 go 且未安装 docker，无法构建 Go Agent" >&2; exit 1; }
  log "宿主无 go，使用 golang 容器构建..."
  mkdir -p "$DIST_DIR"
  # 挂载仓库根，容器内构建到 /src/agent-go/dist
  docker run --rm \
    -v "$REPO_ROOT:/src" \
    -w /src/agent-go \
    -e CGO_ENABLED=0 \
    -e GOFLAGS="-mod=mod" \
    golang:1.24 \
    bash -c '
      set -e
      VERSION="$(cat VERSION 2>/dev/null || echo 0.0.0)"
      for platform in '"$PLATFORMS"'; do
        os="${platform%%/*}"; arch="${platform##*/}"
        echo "[agent-go] 构建 ${os}/${arch}"
        GOOS="$os" GOARCH="$arch" go build -trimpath \
          -ldflags "-s -w -X main.agentVersion=${VERSION}" \
          -o "dist/ops-agent-${os}-${arch}" ./cmd/agent
      done
    '
fi

log "完成，产物："
ls -lh "$DIST_DIR"
