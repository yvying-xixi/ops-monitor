#!/usr/bin/env bash
#
# ops-monitor 备份脚本：MySQL 逻辑备份 + 可选 config/redis/nginx，打包并清理旧归档。
#
# 用法：
#   ./deploy/backup.sh                          # 使用 config.env 中的 BACKUP_* 配置
#   ./deploy/backup.sh --out /data/backups --retention 30
#   ./deploy/backup.sh --include-redis --include-nginx
#   ./deploy/backup.sh --dry-run
#
# 归档内容：
#   mysql.sql.gz      MySQL 逻辑备份
#   config.env        deploy/config.env（含密钥，权限 0600）——除非 --no-config
#   dump.rdb          Redis 快照——仅 --include-redis
#   nginx.tar.gz      nginx 配置与证书——仅 --include-nginx
#   manifest.txt      来源、版本、校验和
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
CONFIG="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.env}"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/docker/compose.yml"

OUT_DIR=""
RETENTION=""
INCLUDE_REDIS=""
INCLUDE_NGINX=""
INCLUDE_CONFIG=""
DRY_RUN=false

log()  { echo -e "\033[32m[backup]\033[0m $*"; }
warn() { echo -e "\033[33m[warn]\033[0m $*"; }
err()  { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT_DIR="${2:-}"; shift 2 ;;
    --retention) RETENTION="${2:-}"; shift 2 ;;
    --include-redis) INCLUDE_REDIS=true; shift ;;
    --include-nginx) INCLUDE_NGINX=true; shift ;;
    --no-config) INCLUDE_CONFIG=false; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) err "未知参数: $1（--help 查看用法）" ;;
  esac
done

command -v docker >/dev/null 2>&1 || err "未安装 docker"
docker compose version >/dev/null 2>&1 || err "docker compose v2 不可用"
command -v gzip >/dev/null 2>&1 || err "缺少 gzip"
command -v tar  >/dev/null 2>&1 || err "缺少 tar"

[ -f "$CONFIG" ] || err "配置文件不存在: $CONFIG"
[ -f "$ENV_FILE" ] || err "环境文件不存在: $ENV_FILE（先执行 ./deploy/prepare.sh）"

# 载入配置（受信任的 Bash 配置文件）
set -a
# shellcheck disable=SC1090
. "$CONFIG"
set +a

BACKUP_DIR="${OUT_DIR:-${BACKUP_DIR:-./backups}}"
RETENTION="${RETENTION:-${BACKUP_RETENTION_DAYS:-14}}"
INCLUDE_CONFIG="${INCLUDE_CONFIG:-${BACKUP_INCLUDE_CONFIG:-true}}"
INCLUDE_REDIS="${INCLUDE_REDIS:-${BACKUP_INCLUDE_REDIS:-false}}"
INCLUDE_NGINX="${INCLUDE_NGINX:-${BACKUP_INCLUDE_NGINX:-false}}"

case "$BACKUP_DIR" in
  /*) : ;;
  *) BACKUP_DIR="$DEPLOY_DIR/$BACKUP_DIR" ;;
esac

[ -n "${DB_NAME:-}" ] || err "config.env 缺少 DB_NAME"
case "$RETENTION" in
  ''|*[!0-9]*) err "保留天数必须为非负整数: $RETENTION" ;;
esac

compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

if [ "$DRY_RUN" = true ]; then
  log "dry-run：将执行以下动作"
  echo "  - 备份 MySQL 数据库: ${DB_NAME}"
  echo "  - 包含 config.env: ${INCLUDE_CONFIG}"
  echo "  - 包含 Redis: ${INCLUDE_REDIS}"
  echo "  - 包含 nginx: ${INCLUDE_NGINX}"
  echo "  - 输出目录: ${BACKUP_DIR}"
  echo "  - 保留天数: ${RETENTION}"
  exit 0
fi

mkdir -p "$BACKUP_DIR"
command -v docker >/dev/null 2>&1
if ! compose exec -T mysql true </dev/null >/dev/null 2>&1; then
  err "mysql 容器未运行（先 ./deploy/install.sh 或 compose up -d mysql）"
fi

STAGING="$(mktemp -d)"
ARCHIVE_NAME="ops-monitor-backup-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
ARCHIVE="$BACKUP_DIR/$ARCHIVE_NAME"
ARCHIVE_TMP="$BACKUP_DIR/.$ARCHIVE_NAME.tmp"
cleanup() { rm -rf "$STAGING" "$ARCHIVE_TMP"; }
trap cleanup EXIT

log "备份 MySQL 数据库 ${DB_NAME} ..."
compose exec -T mysql sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --databases "$MYSQL_DATABASE"' \
  </dev/null | gzip -9 > "$STAGING/mysql.sql.gz"
gzip -t "$STAGING/mysql.sql.gz" || err "MySQL 备份 gzip 校验失败"

if [ "$INCLUDE_CONFIG" = true ]; then
  install -m 600 "$CONFIG" "$STAGING/config.env"
  log "已包含 config.env（含密钥，权限 0600）"
fi

if [ "$INCLUDE_REDIS" = true ]; then
  log "备份 Redis 快照 ..."
  compose exec -T redis sh -c 'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning BGSAVE' </dev/null >/dev/null
  sleep 1
  compose cp redis:/data/dump.rdb "$STAGING/dump.rdb" >/dev/null 2>&1 || warn "Redis dump.rdb 复制失败，跳过"
  [ -f "$STAGING/dump.rdb" ] || warn "未获取到 Redis dump.rdb"
fi

if [ "$INCLUDE_NGINX" = true ]; then
  log "备份 nginx 配置与证书 ..."
  mkdir -p "$STAGING/nginx"
  [ -d "$DEPLOY_DIR/nginx/conf.d" ] && cp -a "$DEPLOY_DIR/nginx/conf.d" "$STAGING/nginx/conf.d"
  [ -d "$DEPLOY_DIR/nginx/certs" ] && cp -a "$DEPLOY_DIR/nginx/certs" "$STAGING/nginx/certs"
  tar czf "$STAGING/nginx.tar.gz" -C "$STAGING" nginx
  rm -rf "$STAGING/nginx"
fi

{
  echo "created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "app_version=$(cat "$REPO_ROOT/VERSION" 2>/dev/null || echo unknown)"
  echo "git_commit=$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "db_name=${DB_NAME}"
  echo "include_config=${INCLUDE_CONFIG}"
  echo "include_redis=${INCLUDE_REDIS}"
  echo "include_nginx=${INCLUDE_NGINX}"
  echo "--- sha256 ---"
  ( cd "$STAGING" && find . -type f ! -name manifest.txt -exec sha256sum {} + )
} > "$STAGING/manifest.txt"

log "打包归档 ..."
tar czf "$ARCHIVE_TMP" -C "$STAGING" .
mv "$ARCHIVE_TMP" "$ARCHIVE"

log "清理超过 ${RETENTION} 天的归档 ..."
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'ops-monitor-backup-*.tar.gz' -mtime "+${RETENTION}" -delete

if [ -n "${BACKUP_POST_CMD:-}" ]; then
  log "执行备份后钩子 BACKUP_POST_CMD"
  ARCHIVE="$ARCHIVE" sh -c "$BACKUP_POST_CMD" || warn "BACKUP_POST_CMD 执行失败"
fi

log "完成：$ARCHIVE"
