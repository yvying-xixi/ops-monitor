# ADR-008: 数据库迁移方案

## Status

Accepted

## Context

项目原先以 `deploy/mysql/init/ops_monitor_schema.sql` 作为 Schema 唯一来源，由 MySQL 容器首启执行；CI 用正则剥离 `CREATE DATABASE` / `USE` 后直接执行该脚本。随着后续需要为任务重试、幂等等功能加列，手工 SQL 无法安全管理 Schema 演进，也没有回滚能力。

同时，ORM 模型（`backend/app/models/`）需要与数据库 Schema 保持一致，否则 `alembic autogenerate` 无法作为可信的差异基准。

## Decision

- 引入 **Alembic**，迁移脚本位于 `backend/migrations/`，`env.py` 以 `Base.metadata` 为 `target_metadata`，连接串取自应用 `settings.database_url`。
- `0001_initial` 由 Alembic **autogenerate** 生成，要求：
  1. 在**真实 SQL 建出的 Schema** 上验证 `alembic check` 报告 **No new upgrade operations detected**（diff = 0）；
  2. 不得为通过校验而手工改写基线模型或迁移文件；差异通过使模型忠实描述真实 Schema 来消除。
- 为使模型忠实，需补齐 `DATETIME(3)`、`TINYINT`、显式索引/唯一约束/外键名，以及生成列 `alert_event.is_active`；`updated_at` 的 `ON UPDATE CURRENT_TIMESTAMP(3)` 通过 `server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)")` 表达（Alchemy 的 `server_onupdate` 不渲染 MySQL DDL）。
- 容器启动由 `backend/entrypoint.sh` 先执行 `alembic upgrade head`，再启动 uvicorn（在 worker 之前执行一次，避免并发迁移）。
- 删除 `deploy/mysql/init/ops_monitor_schema.sql`，Schema 单一来源转为迁移脚本。
- 存量库通过 `alembic stamp 0001_initial` 对齐基线，避免重复建表。

## Alternatives

### 继续手工维护 SQL

- 优点：零新增依赖。
- 缺点：无法可靠追踪 Schema 演进、无回滚、CI 依赖正则 hack。

### 由 SQL 反射生成基线，但保留模型不完整

- 优点：基线可快速匹配现状。
- 缺点：`target_metadata` 与真实 Schema 长期偏离，后续 autogenerate 会产生虚假差异，基准不可信。

## Consequences

### Positive

- Schema 变更可版本化、可回滚（`alembic upgrade/downgrade`）。
- `alembic check` 可作为 CI/开发阶段的 Schema 漂移检测。
- 模型与数据库结构一致，后续 `0002` 的差异可靠。

### Negative

- 新增 Alembic 依赖与迁移目录；开发者本地需先执行 `alembic upgrade head`。
- `ON UPDATE` 采用 `server_default` 技巧表达，注释中需说明。
- 生成列表达式的比较是 Alembic 已知限制（`Computed default ... cannot be modified` 警告可忽略）。

## Alternatives (Superseded)

无。
