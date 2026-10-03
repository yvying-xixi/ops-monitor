#!/usr/bin/env bash
#
# 安装/卸载 ops-monitor 每日备份 systemd timer。
#
# 用法：
#   sudo ./deploy/backup-timer.sh --install
#   sudo ./deploy/backup-timer.sh --uninstall
#
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
UNIT_DIR="/etc/systemd/system"
SERVICE_SRC="$DEPLOY_DIR/systemd/ops-monitor-backup.service"
TIMER_SRC="$DEPLOY_DIR/systemd/ops-monitor-backup.timer"
SERVICE_DST="$UNIT_DIR/ops-monitor-backup.service"
TIMER_DST="$UNIT_DIR/ops-monitor-backup.timer"

log()  { echo -e "\033[32m[backup-timer]\033[0m $*"; }
err()  { echo -e "\033[31m[error]\033[0m $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || err "需要 root 权限（sudo）"
command -v systemctl >/dev/null 2>&1 || err "未找到 systemctl（如使用 cron，请改用文档中的 cron 方式）"

action="${1:-}"
case "$action" in
  --install)
    [ -f "$SERVICE_SRC" ] && [ -f "$TIMER_SRC" ] || err "找不到 systemd 模板: $DEPLOY_DIR/systemd/"
    sed "s|__REPO_DIR__|$REPO_ROOT|g" "$SERVICE_SRC" > "$SERVICE_DST"
    sed "s|__REPO_DIR__|$REPO_ROOT|g" "$TIMER_SRC" > "$TIMER_DST"
    systemctl daemon-reload
    systemctl enable --now ops-monitor-backup.timer
    log "已安装并启用 ops-monitor-backup.timer"
    systemctl list-timers ops-monitor-backup.timer --no-pager || true
    ;;
  --uninstall)
    systemctl disable --now ops-monitor-backup.timer 2>/dev/null || true
    rm -f "$SERVICE_DST" "$TIMER_DST"
    systemctl daemon-reload
    log "已卸载 ops-monitor-backup.timer"
    ;;
  *)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
