# 升级

> 本文描述平台与 Agent 的升级流程。部分步骤需结合实际版本补充。

## 平台升级

```bash
cd /path/to/ops-monitor
git pull                       # 获取新代码
./deploy/check.sh              # 体检
./deploy/reconfigure.sh        # 重新渲染并重建（数据保留）
```

- 配置变更：修改 `deploy/config.env` 后执行 `reconfigure.sh`。
- 使用预构建镜像：在 `config.env` 设置 `IMAGE_REGISTRY` 与 `IMAGE_TAG`，`reconfigure.sh` 会拉取镜像。

## 数据库变更

Schema 由 Alembic 迁移管理，位于 `backend/migrations/`。

- **常规升级**：`reconfigure.sh` 重建 backend 容器时，`entrypoint.sh` 会自动执行 `alembic upgrade head`。
- **手动执行**（本地或排障）：

```bash
cd backend
alembic upgrade head          # 应用全部迁移
alembic current               # 查看当前版本
alembic downgrade -1          # 回滚一步
```

- **存量库首次接入 Alembic**：旧库已由 `ops_monitor_schema.sql` 建表，需对齐基线而**不重复建表**：

```bash
cd backend
alembic stamp 0001_initial    # 标记为已应用基线
alembic upgrade head          # 应用后续迁移
```

- 回滚前请按 [backup.md](backup.md) 备份数据库。

## Agent 升级

升级时**保留** `config.yaml` 与 Ed25519 私钥 `agent_ed25519.key`，仅替换程序并重启：

```bash
# Go Agent：从 Release 或平台安装包获取新二进制
sudo systemctl stop server-agent
sudo install -m 0755 ops-agent /opt/ops-agent/ops-agent    # 替换二进制
sudo systemctl start server-agent

# Python Agent：重新执行 install.sh（--config 指向现有配置）
sudo ./agent/install.sh --config /opt/ops-agent/config/config.yaml
```

- 私钥文件用于请求签名；保留可避免重新注册导致公钥变更。
- 校验：`systemctl status server-agent`、平台服务器详情显示 ONLINE、心跳/指标持续上报；启用签名时确认请求验签通过。

## 兼容性

- **API**：新增字段保持向后兼容；破坏性变更需在 `CHANGELOG.md` 标注并提升平台版本。
- **Agent 协议**：字段级兼容按「新增一律可选、删除/改语义为破坏性」处理，详见 [reference/agent-protocol.md](../reference/agent-protocol.md#兼容性)。
- 平台与 Agent 可独立升级；启用强制签名（`AGENT_REQUIRE_SIGNATURE=true`）前需先升级 Agent。

## 回滚

- **平台**：`git checkout <上一个 tag>` 后 `./deploy/reconfigure.sh`；如新版本含 Schema 变更，按 [backup.md](backup.md) 备份后执行 `alembic downgrade <目标版本>`。
- **Agent**：替换回旧二进制 / 旧代码并重启 `server-agent`。
- **数据**：需要时按 [recovery.md](recovery.md) 从备份恢复。
