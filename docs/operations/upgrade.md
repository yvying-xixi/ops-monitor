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

> **TODO**: 补充 Agent 升级流程（替换代码 → 重启 `server-agent` → 校验注册与上报）。

## 兼容性

> **TODO**: 补充 API 与 Agent 协议的兼容/破坏性变更策略。

## 回滚

> **TODO**: 补充回滚步骤（代码版本与数据卷快照）。
