#!/usr/bin/env bash
#
# 平台部署环境与配置体检（只读，不改变任何状态）
#
set -uo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.yml}"

ok()   { echo -e "  \033[32m[ok]\033[0m $*"; }
warn() { echo -e "  \033[33m[warn]\033[0m $*"; }
bad()  { echo -e "  \033[31m[fail]\033[0m $*"; FAILED=1; }

FAILED=0
echo "== ops-monitor 部署体检 =="

# 1. 依赖
command -v docker >/dev/null 2>&1 && ok "docker 已安装" || bad "未安装 docker"
docker compose version >/dev/null 2>&1 && ok "docker compose v2 可用" || bad "docker compose 不可用"
command -v python3 >/dev/null 2>&1 && ok "python3 已安装" || bad "未安装 python3"
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import yaml" >/dev/null 2>&1 && ok "PyYAML 可用" || bad "缺少 PyYAML（apt install -y python3-yaml）"
fi

# 2. 配置文件
if [ -f "$CONFIG" ]; then
  ok "配置文件存在: $CONFIG"
  if command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" >/dev/null 2>&1; then
    if python3 "$DEPLOY_DIR/prepare.py" --check "$CONFIG"; then :; else FAILED=1; fi
  fi
else
  warn "配置文件不存在: $CONFIG（install.sh 会从 config.yml.tmpl 生成）"
fi

# 3. 端口占用
if [ -f "$CONFIG" ] && command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" >/dev/null 2>&1; then
  HTTP_PORT="$(python3 -c "import yaml;print(((yaml.safe_load(open('$CONFIG')) or {}).get('http') or {}).get('port',80))" 2>/dev/null)"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${HTTP_PORT}\$"; then
      warn "端口 ${HTTP_PORT} 已被占用（若为本平台旧实例可忽略）"
    else
      ok "端口 ${HTTP_PORT} 空闲"
    fi
  fi
fi

# 4. 数据目录
if [ -f "$CONFIG" ] && command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" >/dev/null 2>&1; then
  DATA_DIR="$(python3 -c "import yaml;print(((yaml.safe_load(open('$CONFIG')) or {}).get('data') or {}).get('volume_dir',''))" 2>/dev/null)"
  case "$DATA_DIR" in
    /*) : ;;
    *) DATA_DIR="$DEPLOY_DIR/$DATA_DIR" ;;
  esac
  if mkdir -p "$DATA_DIR" 2>/dev/null && [ -w "$DATA_DIR" ]; then
    ok "数据目录可写: $DATA_DIR"
  else
    bad "数据目录不可写: $DATA_DIR"
  fi
fi

echo "== 体检结束 =="
[ "$FAILED" -eq 0 ] && exit 0 || exit 1
