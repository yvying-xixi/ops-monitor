# 恢复

> 本文描述平台数据与配置的恢复流程：首选 `deploy/restore.sh`，附手动备选与演练清单。

## 自动恢复（推荐）

```bash
# 默认仅恢复 MySQL（交互确认）
./deploy/restore.sh ops-monitor-backup-<UTC>.tar.gz

# 跳过确认
./deploy/restore.sh <archive> --yes

# 附加恢复 Redis 快照
./deploy/restore.sh <archive> --redis

# 恢复部署配置（覆盖 config.env）
./deploy/restore.sh <archive> --config
```

要点：

- 恢复前会校验归档 `manifest.txt` 的 sha256；不匹配则中止。
- **默认仅恢复 MySQL**；`--redis` 才恢复 Redis。
- `--config` 恢复 `config.env` 需**强确认**（输入 `RESTORE CONFIG`），并在覆盖前把当前 `config.env` 快照到 `BACKUP_DIR/config.env.pre-restore-<UTC>`。
- 恢复期间停止 `backend` 容器避免写入；完成后重启并做健康检查。
- 若恢复了 `config.env`，执行 `./deploy/reconfigure.sh` 使新配置生效。

## 手动恢复（备选）

### 从 SQL 逻辑备份恢复

```bash
docker compose -f deploy/docker/compose.yml --env-file deploy/.env up -d mysql
gunzip -c mysql.sql.gz | \
  docker compose -f deploy/docker/compose.yml --env-file deploy/.env exec -T mysql \
  sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'
```

### 从数据目录备份恢复

```bash
cd /path/to/ops-monitor
docker compose -f deploy/docker/compose.yml --env-file deploy/.env down
tar xzf ops-monitor-data-<date>.tar.gz -C deploy
docker compose -f deploy/docker/compose.yml --env-file deploy/.env up -d
```

## 配置恢复

- 恢复 `deploy/config.env` 后执行 `./deploy/reconfigure.sh` 重新渲染并重建。
- Agent 配置恢复后重启 `server-agent`。

## 验证

1. `docker compose -f deploy/docker/compose.yml --env-file deploy/.env ps` 全部 healthy。
2. `curl http://<host>:<port>/api/v1/health`。
3. 登录并抽查服务器/指标/告警数据。

## 恢复演练清单

- [ ] 从**最新归档**恢复到**独立环境**（不覆盖生产），验证数据完整。
- [ ] 记录 RTO（恢复耗时）与 RPO（可接受的数据丢失窗口）。
- [ ] 验证 `config.env` 快照可用、密钥可正常启动。
- [ ] 验证 Agent 重连后心跳/指标恢复上报。

## TODO

> **TODO**: 补充灾难恢复（整机重建）步骤与演练记录模板。
> **TODO**: 补充恢复后 Agent 重连与数据一致性校验。
