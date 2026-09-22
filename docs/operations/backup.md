# 备份

> 本文描述平台数据与配置的备份方式。

## 备份对象

| 对象 | 位置 | 说明 |
| --- | --- | --- |
| MySQL 数据 | `data.volume_dir/mysql` | 业务与监控数据 |
| Redis 数据 | `data.volume_dir/redis` | 缓存/任务状态 |
| 部署配置 | `deploy/config.yml` | 配置源（含密钥，妥善保管） |
| 部署环境变量 | `deploy/.env` | 渲染产物 |
| Agent 配置 | 各服务器 `agent/config/config.yaml` | 含 Token |

`data.volume_dir` 由 `deploy/config.yml` 的 `data.volume_dir` 指定（默认 `deploy/data`）。

```mermaid
flowchart LR
    A[停止服务 down] --> B[打包 data.volume_dir]
    B --> C[保存归档]
    C --> D[启动服务 up -d]
```

## 备份方式

### 停止服务后备份数据目录（简单可靠）

```bash
cd /path/to/ops-monitor
docker compose --env-file deploy/.env down
tar czf ops-monitor-data-$(date +%F).tar.gz -C deploy data
docker compose --env-file deploy/.env up -d
```

### 仅备份数据库（逻辑备份）

```bash
docker compose --env-file deploy/.env exec -T mysql \
  mysqldump -uroot -p"$DB_PASSWORD" --databases ops_monitor > ops_monitor-$(date +%F).sql
```

> `$DB_PASSWORD` 取自 `deploy/.env`。

## 恢复

见 [recovery.md](recovery.md)。

## TODO

> **TODO**: 补充定时备份与保留策略（cron/脚本）。
