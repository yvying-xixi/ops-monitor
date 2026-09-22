# 文档总入口

本目录是 `ops-monitor` 的长期知识库。文档按**读者要解决的问题**组织，而非按开发阶段编号组织。

## 文档分类

| 目录 | 回答的问题 | 内容 |
| --- | --- | --- |
| [getting-started/](getting-started/) | 我如何开始开发？ | 环境准备、本地启动、首次贡献 |
| [architecture/](architecture/) | 系统为什么这样设计？ | 系统边界、组件关系、数据流、安全模型 |
| [modules/](modules/) | 某个功能如何工作？ | 认证、权限、服务器管理、监控、告警、服务管理、自动化、审计 |
| [reference/](reference/) | 具体参数、API 或 Schema 是什么？ | API 规范、数据库、配置、Agent 协议、错误码、端口 |
| [operations/](operations/) | 如何部署、升级和排错？ | 部署、Agent 部署、升级、备份、恢复、平台可观测性、排错 |
| [decisions/](decisions/) | 为什么当初这样设计？ | 架构决策记录（ADR） |
| [CHANGELOG](../CHANGELOG.md) | 版本发生了什么变化？ | 版本变更历史 |

### 两个 `monitoring` 的边界

```text
modules/monitoring.md      监控被管理的服务器和服务（业务监控）
operations/monitoring.md   监控 ops-monitor 平台自身（可观测性）
```

## 文档规则

1. **以当前代码为事实来源**：文档描述当前实际行为，而非历史设计或计划行为。
2. **信息不足使用 `TODO`**：无法确认的内容标注 `> **TODO**`，不进行推测性补全。
3. **代码与文档同步变更**：行为变化时同步更新相关文档（见 [CONTRIBUTING](../CONTRIBUTING.md)）。
4. **API 以 OpenAPI 为权威**：`reference/api.md` 只写通用规范并指向 `/docs`；模块文档保留精简接口表。
5. **不再创建阶段文档**：不新增 `phaseX-xxx.md`；历史变化写入 `CHANGELOG.md` 与 `decisions/`。
6. **文件名使用英文小写短横线**，正文使用中文。
7. **重要技术决策使用 ADR**，位于 `decisions/`。

## 查找文档欠账

```bash
grep -R "TODO" docs/
```
