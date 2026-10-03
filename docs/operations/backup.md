# 备份

> 本文描述平台数据与配置的备份方式：`deploy/backup.sh` 自动化备份与保留策略。

## 备份对象

| 对象 | 默认 | 说明 |
| --- | --- | --- |
| MySQL 数据 | ✅ | `mysqldump --single-transaction` 逻辑备份（在线一致） |
| 部署配置 `deploy/config.env` | ✅ | 含密钥，归档内权限 0600 |
| Redis | 可选 | 仅缓存/防重放/健康，默认不备份（`BACKUP_INCLUDE_REDIS=true` 开启） |
| nginx 配置与证书 | 可选 | `BACKUP_INCLUDE_NGINX=true` 开启 |
| Agent 配置 | ❌ | 各主机本地，Token 可再生，不集中备份 |

## 配置（`deploy/config.env`）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `BACKUP_DIR` | `./backups` | 归档目录（相对 `deploy/` 或绝对路径） |
| `BACKUP_RETENTION_DAYS` | 14 | 保留天数，超期归档自动删除 |
| `BACKUP_INCLUDE_CONFIG` | true | 是否包含 `config.env` |
| `BACKUP_INCLUDE_REDIS` | false | 是否包含 Redis 快照 |
| `BACKUP_INCLUDE_NGINX` | false | 是否包含 nginx 配置与证书 |
| `BACKUP_POST_CMD` | 空 | 备份后钩子，可读取 `$ARCHIVE`（如异地同步） |

## 手动执行

```bash
./deploy/backup.sh                 # 按 config.env 的 BACKUP_* 配置
./deploy/backup.sh --dry-run       # 仅打印将执行的动作
./deploy/backup.sh --out /data/backups --retention 30
./deploy/backup.sh --include-redis --include-nginx
./deploy/backup.sh --no-config
```

前置：`deploy/config.env` 与 `deploy/.env` 已存在（先 `./deploy/prepare.sh` 或 `install.sh`），mysql 容器运行中。

### 归档内容

`ops-monitor-backup-<UTC>.tar.gz`：

```text
mysql.sql.gz     MySQL 逻辑备份
config.env       config.env（含密钥，0600）——若包含
dump.rdb         Redis 快照——若包含
nginx.tar.gz     nginx 配置与证书——若包含
manifest.txt     创建时间、版本、git commit、DB 名、sha256 校验和
```

## 定时备份

### systemd timer（推荐）

```bash
sudo ./deploy/backup-timer.sh --install     # 每日 03:30 + 随机延迟
systemctl list-timers ops-monitor-backup.timer
sudo ./deploy/backup-timer.sh --uninstall
```

### cron 备选

```cron
30 3 * * * /path/to/ops-monitor/deploy/backup.sh >> /var/log/ops-monitor-backup.log 2>&1
```

## 异地保存

通过 `BACKUP_POST_CMD` 钩子接入外部存储，例如：

```bash
BACKUP_POST_CMD='rclone sync "$ARCHIVE" remote:ops-monitor-backups'
```

## 恢复

见 [recovery.md](recovery.md)（`deploy/restore.sh`）。

## 风险提示

- **归档含密钥**：`config.env` 等同平台密钥，请置于受控目录并限制权限。
- 失败告警：脚本失败返回非零；建议结合监控/告警接入（如 systemd `OnFailure`）。
