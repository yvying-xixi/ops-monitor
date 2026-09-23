# 恢复

> 本文描述平台数据与配置的恢复流程。部分步骤需结合实际环境补充。

```mermaid
flowchart LR
    A[停止服务 down] --> B[还原 data.volume_dir / 导入 SQL]
    B --> C[恢复 config.yml → reconfigure.sh]
    C --> D[启动并验证 health/数据]
```

## 数据恢复

### 从数据目录备份恢复

```bash
cd /path/to/ops-monitor
docker compose -f deploy/docker/compose.yml --env-file deploy/.env down
# 还原备份到 data.volume_dir（默认 deploy/data）
tar xzf ops-monitor-data-<date>.tar.gz -C deploy
docker compose -f deploy/docker/compose.yml --env-file deploy/.env up -d
```

### 从 SQL 逻辑备份恢复

```bash
docker compose -f deploy/docker/compose.yml --env-file deploy/.env up -d mysql
cat ops_monitor-<date>.sql | \
  docker compose -f deploy/docker/compose.yml --env-file deploy/.env exec -T mysql \
  mysql -uroot -p"$DB_PASSWORD"
```

## 配置恢复

- 恢复 `deploy/config.yml` 后执行 `./deploy/reconfigure.sh` 重新渲染并重建。
- Agent 配置恢复后重启 `server-agent`。

## 验证

1. `docker compose -f deploy/docker/compose.yml --env-file deploy/.env ps` 全部 healthy。
2. `curl http://<host>:<port>/api/v1/health`。
3. 登录并抽查服务器/指标/告警数据。

## TODO

> **TODO**: 补充灾难恢复（整机重建）步骤与演练清单。
> **TODO**: 补充恢复后 Agent 重连与数据一致性校验。
