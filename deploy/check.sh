#!/usr/bin/env bash
#
# 平台部署环境与配置体检（只读，不改变任何状态）
#
set -uo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.env}"

ok()   { echo -e "  \033[32m[ok]\033[0m $*"; }
warn() { echo -e "  \033[33m[warn]\033[0m $*"; }
bad()  { echo -e "  \033[31m[fail]\033[0m $*"; FAILED=1; }

FAILED=0
echo "== ops-monitor 部署体检 =="

# 1. 依赖
command -v docker >/dev/null 2>&1 && ok "docker 已安装" || bad "未安装 docker"
docker compose version >/dev/null 2>&1 && ok "docker compose v2 可用" || bad "docker compose 不可用"
for tool in sed od tr; do
  command -v "$tool" >/dev/null 2>&1 && ok "$tool 可用" || bad "缺少 $tool"
done

# 2. 配置文件
if [ -f "$CONFIG" ]; then
  ok "配置文件存在: $CONFIG"
  "$DEPLOY_DIR/prepare.sh" --check || FAILED=1
elif [ -f "$DEPLOY_DIR/config.yml" ]; then
  warn "检测到旧配置 deploy/config.yml，请先运行 ./deploy/install.sh 完成迁移"
else
  warn "配置文件不存在: $CONFIG（install.sh 会从 config.env.tmpl 生成）"
fi

# 3/4. 端口与数据目录（source config.env；只读校验，不创建目录）
if [ -f "$CONFIG" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$CONFIG"
  set +a

  HTTP_PORT="${HTTP_PORT:-80}"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${HTTP_PORT}\$"; then
      warn "端口 ${HTTP_PORT} 已被占用（若为本平台旧实例可忽略）"
    else
      ok "端口 ${HTTP_PORT} 空闲"
    fi
  fi

  DATA_DIR="${DATA_VOLUME_DIR:-}"
  case "$DATA_DIR" in
    /*) : ;;
    *) DATA_DIR="$DEPLOY_DIR/$DATA_DIR" ;;
  esac
  if [ -d "$DATA_DIR" ]; then
    [ -w "$DATA_DIR" ] && ok "数据目录可写: $DATA_DIR" || bad "数据目录不可写: $DATA_DIR"
  else
    PARENT="$(dirname "$DATA_DIR")"
    if [ -d "$PARENT" ] && [ -w "$PARENT" ]; then
      ok "数据目录待创建（父目录可写）: $DATA_DIR"
    else
      bad "数据目录父级不可写: $PARENT"
    fi
  fi
fi

echo "== 体检结束 =="
[ "$FAILED" -eq 0 ] && exit 0 || exit 1
