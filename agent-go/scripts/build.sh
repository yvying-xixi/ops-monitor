#!/usr/bin/env bash
#
# 交叉编译 Go Agent 到 dist/（默认 linux/amd64 与 linux/arm64）
#
# 用法：
#   ./agent-go/scripts/build.sh                # 构建两个架构，版本取 agent-go/VERSION
#   VERSION=1.2.3 ./agent-go/scripts/build.sh  # 指定版本
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${AGENT_DIR}/dist"
VERSION="${VERSION:-$(cat "${AGENT_DIR}/VERSION" 2>/dev/null || echo "0.0.0")}"
PLATFORMS="${PLATFORMS:-linux/amd64 linux/arm64}"

log() { echo -e "\033[32m[build]\033[0m $*"; }

command -v go >/dev/null 2>&1 || { echo "[error] 未找到 go 命令" >&2; exit 1; }

mkdir -p "$DIST_DIR"

cd "$AGENT_DIR"
export CGO_ENABLED=0
LDFLAGS="-s -w -X main.agentVersion=${VERSION}"

for platform in $PLATFORMS; do
  os="${platform%%/*}"
  arch="${platform##*/}"
  out="${DIST_DIR}/ops-agent-${os}-${arch}"
  log "构建 ${os}/${arch} -> ${out}"
  GOOS="$os" GOARCH="$arch" go build -trimpath -ldflags "$LDFLAGS" -o "$out" ./cmd/agent
done

log "完成，产物位于 ${DIST_DIR}"
ls -lh "$DIST_DIR"
