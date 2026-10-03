# Remaining Documentation TODOs

> 本文档汇总当前文档欠账。可通过 `grep -R "TODO" docs/` 核对。
>
> 工程优化路线（代码、CI、可观测性、安全）见 [`optimization-plan.md`](optimization-plan.md)；本文只保留文档类欠账，与之重叠的条目以 `optimization-plan.md` 为准。

## Architecture

- [ ] 补充生产环境网络拓扑（HTTPS、反向代理、多主机）。
- [ ] 完成 data-flow 中前端各页面数据依赖与刷新周期。
- [ ] 补充 Agent 重连后的数据一致性策略。
- [x] 密钥轮换：公钥在线轮换已实现（[ADR-010](decisions/010-agent-request-signing.md)、`POST /api/v1/agent/signing-key`）。
- [ ] 补充 Token 撤销与最小权限清单。

## Agent

- [x] 协议版本号与向后兼容策略（[agent-protocol.md](reference/agent-protocol.md#compatibility)）。
- [x] 升级流程与协议兼容矩阵（[upgrade.md](operations/upgrade.md)、agent-protocol）。
- [x] 确认任务轮询的幂等性规则（[ADR-009](decisions/009-task-retry-and-idempotency.md)）。

## Reference

- [ ] 确认 API Base URL 与生产访问路径（OpenAPI 入口）。
- [ ] 补充分页/过滤/排序/幂等/时间格式的细节。
- [x] 归档策略：原始指标 7 天 → 日聚合归档 180 天；表含外键故不做 MySQL 分区（[monitoring.md](operations/monitoring.md#指标生命周期与归档)）。
- [ ] 补全传递依赖许可证清单（项目许可证已定为 Apache-2.0）。

## Operations

- [x] 升级流程（平台/数据库/Agent）与回滚步骤（[upgrade.md](operations/upgrade.md)）。
- [x] 定时备份与保留策略（[backup.md](operations/backup.md)）。
- [x] 灾难恢复步骤与演练清单（[recovery.md](operations/recovery.md)）。
- [x] 平台自身可观测性（Prometheus `/metrics` + OpenTelemetry，见 [monitoring.md](operations/monitoring.md)）。
- [ ] 完成故障排查矩阵。

## Governance

- [x] 确认最终项目许可证并新增 `LICENSE`（Apache-2.0，见根目录 `LICENSE`）。
- [ ] 评估是否需要 OpenAPI 一致性检查。
- [x] 补充 PR 模板与 Reviewer 检查清单（[PR 模板](../.github/pull_request_template.md)）。
