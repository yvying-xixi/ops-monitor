# 首次贡献

> 本文面向第一次参与本项目的贡献者。完整规范见 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

## 流程概览

```text
Fork/Clone → 建分支 → 开发 → 测试 → 更新文档 → 提交 PR
```

## 建议步骤

1. 阅读 [architecture/overview.md](../architecture/overview.md) 了解系统结构。
2. 按 [local-environment.md](local-environment.md) 搭建环境并跑通测试。
3. 从 `master` 切功能分支（`feature/xxx`、`fix/xxx`）。
4. 遵循提交规范（`<type>(<scope>): <subject>`）。
5. 代码变更影响 API/数据库/Agent 协议/配置/部署/架构时，**同步更新文档**。
6. 运行测试与文档检查后提交 PR。

## 检查清单

- [ ] 分支命名规范
- [ ] 提交信息规范
- [ ] 测试通过（backend/agent/frontend）
- [ ] 相关文档已更新
- [ ] 无 `TODO` 遗漏（如涉及未确认内容）

## TODO

> **TODO**: 补充 PR 模板与 Reviewer 检查清单。
