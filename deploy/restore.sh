#!/usr/bin/env bash
#
# ops-monitor 恢复脚本：默认仅恢复 MySQL；--config 覆盖 config.env（需强确认）；
# --redis 恢复 Redis 快照。
#
# 用法：
#   ./deploy/restore.sh ops-monitor-backup-20260101T030000Z.tar.gz
#   ./deploy/restore.sh <archive> --yes
#   ./deploy/restore.sh <archive> --config      # 强确认后覆盖 config.env（先快照当前配置）
#   ./deploy/restore.sh <archive> --redis
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.env}"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/docker/compose.yml"

ARCHIVE=""
ASSUME_YES=false
RESTORE_CONFIG=false
RESTORE_REDIS=false

log()  { echo -e "\033[32m[restore]\033[0m $*"; }
warn() { echo -e "\033[33m[warn]\033[0m $*"; }
err()  { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --yes) ASSUME_YES=true; shift ;;
    --config) RESTORE_CONFIG=true; shift ;;
    --redis) RESTORE_REDIS=true; shift ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) err "未知参数: $1（--help 查看用法）" ;;
    *) [ -z "$ARCHIVE" ] || err "重复的归档参数"; ARCHIVE="$1"; shift ;;
  esac
done

[ -n "$ARCHIVE" ] || err "用法: ./deploy/restore.sh <archive.tar.gz> [--yes] [--config] [--redis]"
[ -f "$ARCHIVE" ] || err "归档不存在: $ARCHIVE"
command -v docker >/dev/null 2>&1 || err "未安装 docker"
docker compose version >/dev/null 2>&1 || err "docker compose v2 不可用"
command -v sha256sum >/dev/null 2>&1 || err "缺少 sha256sum"
[ -f "$CONFIG" ] || err "配置文件不存在: $CONFIG"

set -a
# shellcheck disable=SC1090
. "$CONFIG"
set +a

BACKUP_DIR="${BACKUP_DIR:-./backups}"
case "$BACKUP_DIR" in
  /*) : ;;
  *) BACKUP_DIR="$DEPLOY_DIR/$BACKUP_DIR" ;;
esac

compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

STAGING="$(mktemp -d)"
cleanup() { rm -rf "$STAGING"; }
trap cleanup EXIT

log "解包归档 ..."
tar xzf "$ARCHIVE" -C "$STAGING"
[ -f "$STAGING/mysql.sql.gz" ] || err "归档缺少 mysql.sql.gz"
[ -f "$STAGING/manifest.txt" ] || err "归档缺少 manifest.txt"

log "校验归档完整性 ..."
if grep -q '^--- sha256 ---$' "$STAGING/manifest.txt"; then
  sed -n '/^--- sha256 ---$/,$p' "$STAGING/manifest.txt" | tail -n +2 > "$STAGING/checks.sha"
  ( cd "$STAGING" && sha256sum -c checks.sha >/dev/null ) || err "归档校验和不匹配"
  log "校验和通过"
else
  warn "manifest 无校验和，跳过完整性校验"
fi

echo "---- manifest ----"
cat "$STAGING/manifest.txt"
echo "------------------"

if [ "$ASSUME_YES" != true ]; then
  printf '确认恢复 MySQL 数据库？输入 yes 继续: '
  read -r answer
  [ "$answer" = "yes" ] || err "已取消"
fi

# 停止 backend，避免恢复期间写入
if compose ps --status running -q backend >/dev/null 2>&1 && [ -n "$(compose ps --status running -q backend)" ]; then
  log "停止 backend 容器 ..."
  compose stop backend >/dev/null
fi

log "确保 mysql 运行 ..."
compose up -d mysql >/dev/null
for _ in $(seq 1 30); do
  if compose exec -T mysql sh -c 'mysqladmin ping -h127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" --silent' </dev/null >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

log "导入 MySQL 数据 ..."
gunzip -c "$STAGING/mysql.sql.gz" | \
  compose exec -T mysql sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'

if [ "$RESTORE_REDIS" = true ] && [ -f "$STAGING/dump.rdb" ]; then
  log "恢复 Redis 快照 ..."
  compose stop redis >/dev/null 2>&1 || true
  if compose cp "$STAGING/dump.rdb" redis:/data/dump.rdb >/dev/null 2>&1; then
    compose up -d redis >/dev/null
  else
    warn "Redis dump.rdb 写入失败，跳过"
  fi
fi

if [ "$RESTORE_CONFIG" = true ]; then
  if [ ! -f "$STAGING/config.env" ]; then
    err "--config 指定但归档不含 config.env"
  fi
  warn "即将覆盖 $CONFIG（含密钥）。输入 RESTORE CONFIG 确认: "
  printf '> '
  read -r answer
  [ "$answer" = "RESTORE CONFIG" ] || err "已取消 config 恢复"
  mkdir -p "$BACKUP_DIR"
  SNAPSHOT="$BACKUP_DIR/config.env.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
  install -m 600 "$CONFIG" "$SNAPSHOT"
  log "当前配置已快照: $SNAPSHOT"
  install -m 600 "$STAGING/config.env" "$CONFIG"
  log "已覆盖 config.env；如需生效请执行 ./deploy/reconfigure.sh"
fi

log "启动服务 ..."
compose up -d >/dev/null

log "健康检查 ..."
sleep 3
if compose exec -T backend curl -fsS http://127.0.0.1:8000/api/v1/health </dev/null >/dev/null 2>&1; then
  log "backend /health 正常"
else
  warn "backend 健康检查未通过，请查看 compose ps / 日志"
fi

log "恢复完成"
