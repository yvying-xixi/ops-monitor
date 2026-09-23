#!/usr/bin/env bash
#
# 一次性迁移：deploy/config.yml（旧 YAML）→ deploy/config.env（KV）
#
# 说明：
#   - 仅支持本项目当前固定 schema 的 config.yml；复杂手改 YAML 不保证完整兼容。
#   - 迁移会**逐项保留**原有密钥（DB/Redis/JWT/管理员/HTTPS），不重新生成。
#   - 迁移后请人工复核 config.env；原 config.yml 保留为备份。
#
# 用法：
#   ./deploy/migrate-config.sh
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${DEPLOY_CONFIG_YML:-$DEPLOY_DIR/config.yml}"
OUT="${DEPLOY_CONFIG:-$DEPLOY_DIR/config.env}"

log() { echo -e "\033[32m[migrate]\033[0m $*"; }
err() { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

[ -f "$SRC" ] || err "未找到旧配置: $SRC"
if [ -f "$OUT" ]; then
  log "目标已存在，跳过迁移: $OUT"
  exit 0
fi

# 从旧 YAML 读取值：yget <section> <key>（section 为空表示顶层键）
yget() {
  local sec="$1" key="$2"
  awk -v sec="$sec" -v key="$key" '
    function clean(v) {
      sub(/^[[:space:]]+/, "", v); sub(/[[:space:]]+$/, "", v);
      if (v !~ /^["'"'"']/) { sub(/[[:space:]]+#.*$/, "", v); sub(/[[:space:]]+$/, "", v); }
      if (v ~ /^".*"$/) { v = substr(v, 2, length(v)-2); }
      else if (v ~ /^'"'"'.*'"'"'$/) { v = substr(v, 2, length(v)-2); }
      return v
    }
    BEGIN { insec = (sec == "") ? 1 : 0 }
    sec != "" && $0 ~ ("^" sec ":[[:space:]]*$") { insec = 1; next }
    sec != "" && insec && $0 ~ /^[^[:space:]]/ { insec = 0 }
    insec {
      pat = (sec == "") ? ("^" key ":[[:space:]]*") : ("^[[:space:]]+" key ":[[:space:]]*")
      if ($0 ~ pat) { v = $0; sub(pat, "", v); print clean(v); exit }
    }
  ' "$SRC"
}

emit() { printf '%s=%q\n' "$1" "$2"; }

umask 077
{
  echo "# 由 deploy/migrate-config.sh 从 config.yml 迁移生成"
  echo "# 说明：已保留原有密钥；请人工复核后再删除旧 config.yml"
  echo ""
  echo "# 平台对外访问地址"
  emit HOSTNAME "$(yget "" hostname)"
  echo ""
  echo "# HTTP"
  emit HTTP_PORT "$(yget http port)"
  echo ""
  echo "# HTTPS"
  emit HTTPS_ENABLED "$(yget https enabled)"
  emit HTTPS_PORT "$(yget https port)"
  emit HTTPS_CERTIFICATE "$(yget https certificate)"
  emit HTTPS_PRIVATE_KEY "$(yget https private_key)"
  echo ""
  echo "# 数据库"
  emit DB_NAME "$(yget database name)"
  emit DB_PASSWORD "$(yget database password)"
  echo ""
  echo "# Redis"
  emit REDIS_PASSWORD "$(yget redis password)"
  echo ""
  echo "# JWT"
  emit JWT_SECRET_KEY "$(yget jwt secret_key)"
  emit JWT_EXPIRE_MINUTES "$(yget jwt expire_minutes)"
  echo ""
  echo "# 初始管理员"
  emit SEED_ADMIN_USERNAME "$(yget admin username)"
  emit SEED_ADMIN_PASSWORD "$(yget admin password)"
  echo ""
  echo "# 运行"
  emit SEED_INIT_DATA "$(yget seed init)"
  emit METRIC_RETENTION_DAYS "$(yget metrics retention_days)"
  emit OPERATION_LOG_ENABLED "$(yget operation_log enabled)"
  echo ""
  echo "# 镜像"
  emit IMAGE_REGISTRY "$(yget image registry)"
  emit IMAGE_TAG "$(yget image tag)"
  echo ""
  echo "# 数据目录"
  emit DATA_VOLUME_DIR "$(yget data volume_dir)"
} > "$OUT"
chmod 600 "$OUT"

log "已迁移: $SRC → $OUT"
log "已保留原密钥；请人工复核 config.env"
