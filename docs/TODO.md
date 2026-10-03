# Remaining Documentation TODOs

> 本文档汇总当前文档欠账。可通过 `grep -R "TODO" docs/` 核对。
>
> 工程优化路线（代码、CI、可观测性、安全）见 [`optimization-plan.md`](optimization-plan.md)；本文只保留文档类欠账，与之重叠的条目以 `optimization-plan.md` 为准。

## Architecture

- [ ] 补充生产环境网络拓扑（HTTPS、反向代理、多主机）。
- [ ] 完成 data-flow 中前端各页面数据依赖与刷新周期。
- [ ] 补充 Agent 重连后的数据一致性策略。
- [ ] 补充安全边界的密钥轮换/Token 撤销与最小权限清单。

## Agent

- [ ] 补充协议版本号与向后兼容策略。
- [ ] 补充升级流程与协议兼容矩阵。
- [x] 确认任务轮询的幂等性规则（每次尝试独立执行 + `Idempotency-Key` + 结果重放，见 [ADR-009](decisions/009-task-retry-and-idempotency.md)）。

## Reference

- [ ] 确认 API Base URL 与生产访问路径（OpenAPI 入口）。
- [ ] 补充分页/过滤/排序/幂等/时间格式的细节。
- [ ] 补充数据库索引执行计划验证与归档/分区策略。
- [ ] 补全传递依赖许可证清单（项目许可证已定为 Apache-2.0）。

## Operations

- [ ] 完成升级流程（平台/数据库/Agent）与回滚步骤。
- [ ] 完成定时备份与保留策略。
- [ ] 完成灾难恢复步骤与演练清单。
- [ ] 完成平台自身可观测性（资源/延迟/错误率/自监控）。
- [ ] 完成故障排查矩阵。

## Governance

- [x] 确认最终项目许可证并新增 `LICENSE`（Apache-2.0，见根目录 `LICENSE`）。
- [ ] 评估是否需要 OpenAPI 一致性检查。
- [ ] 补充 PR 模板与 Reviewer 检查清单。
