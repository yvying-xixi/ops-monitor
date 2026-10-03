## 变更说明

<!-- 背景、做了什么、影响范围 -->

## 类型

- [ ] feat
- [ ] fix
- [ ] refactor
- [ ] docs
- [ ] chore / ci
- [ ] security

## 提交者检查清单

- [ ] 已关联相关 Issue / 文档
- [ ] Backend：`cd backend && ruff check app && mypy && pytest app/test -q` 通过
- [ ] Agent（Python / Go）与 Frontend（lint / test / build）按改动范围通过
- [ ] 文档已同步（模块 / 参考 / 运维 / README / CHANGELOG）
- [ ] 涉及 Schema：新增 Alembic 迁移，且 `alembic check` 差异为 0
- [ ] 涉及架构决策：新增 / 更新 ADR
- [ ] 未提交任何密钥 / Token / 明文凭证

## Reviewer 检查清单

- [ ] 变更与描述一致，范围单一
- [ ] 无破坏性变更，或已说明兼容与升级路径
- [ ] 新增逻辑有测试覆盖
- [ ] 迁移可升级且可回滚
- [ ] 安全：输入校验、权限、敏感信息处理得当
