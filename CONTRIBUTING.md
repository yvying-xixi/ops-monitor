# Contributing

感谢参与 `ops-monitor`。本文规定开发、测试、提交与文档要求。

## Development Environment

见 [docs/getting-started/local-environment.md](docs/getting-started/local-environment.md)。

## Branch Strategy

- 从 `master` 切分支：`feature/xxx`、`fix/xxx`、`docs/xxx`、`ci/xxx`。
- 每个分支保持单一职责，稳定后合并。

## Commit Convention

格式：`<type>(<scope>): <subject>`

- `feat`：新功能
- `fix`：修复
- `docs`：文档
- `ci`：CI/构建
- `chore`：杂项
- `refactor`：重构

示例：`feat(auth): 新增登录接口`、`fix(metric): 修复磁盘使用率计算`。

## Pull Request

- 说明变更内容与影响范围。
- 关联相关文档更新。
- 通过测试与文档检查。

## Testing

```bash
cd backend && .venv/bin/python -m pytest app/test/ -q
agent/.venv/bin/python -m pytest agent/tests/ -q
cd frontend && npm run build
```

## Database Changes

- 表结构变更需同步 `sql/ops_monitor_schema.sql` 与 [docs/reference/database.md](docs/reference/database.md)。
- 索引/字段变更需说明查询场景。

## API Changes

- API Schema 以代码与 OpenAPI 为权威；变更需同步模块文档的精简接口表。
- 破坏性变更需在 [CHANGELOG.md](CHANGELOG.md) 标注。

## Agent Protocol Changes

- 协议变更需同步 [docs/reference/agent-protocol.md](docs/reference/agent-protocol.md)。
- 需考虑向后兼容与升级路径。

## Documentation Requirements

| 变更类型 | 是否必须更新文档 |
| --- | --- |
| 修改 API | 必须 |
| 修改数据库 Schema | 必须 |
| 修改 Agent 协议 | 必须 |
| 新增用户功能 | 必须 |
| 修改配置 | 必须 |
| 修改部署方式 | 必须 |
| 修改系统架构 | 必须，并更新或新增 ADR |
| 修复内部 Bug | 通常不需要 |
| 内部重构 | 根据影响决定 |
| 修改 UI 样式 | 通常不需要 |

流程：

```text
代码改变行为 → 检查相关文档 → 同步修改 → 运行测试与文档检查 → 提交 PR
```

## Documentation Rules

1. 以当前代码行为为准，不写历史/计划行为。
2. 信息不足使用 `> **TODO**`，不推测补全。
3. 不新增 `phaseX-xxx.md`；历史变化写入 `CHANGELOG.md` 与 `docs/decisions/`。
4. 文件名英文小写短横线，正文中文。
5. 查找欠账：`grep -R "TODO" docs/`。
