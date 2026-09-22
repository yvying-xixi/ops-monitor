# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格。

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.1.0] - 2026-09-23

首个已交付版本。

### Added

- Backend：FastAPI 应用、统一响应与异常、JWT 认证、RBAC 鉴权、操作审计中间件。
- Agent：系统指标/服务状态采集、注册/心跳/指标/资产/服务上报、受控任务执行。
- 前端：Vue 3 管理端（登录、Dashboard、服务器管理、监控图表、告警中心、任务中心、用户管理）。
- 服务器资产管理：注册、凭证、在线状态（心跳判定）。
- 监控：指标查询（latest/history/summary）、分桶聚合与网络速率差分、Dashboard。
- 告警：阈值规则、事件状态机、确认/恢复、默认规则。
- 服务管理：服务状态监控、受控启停/重启/日志、白名单。
- 自动化任务：单机/批量/定时、执行记录与日志。
- 部署：Docker 镜像、Docker Compose 配置化部署（`deploy/config.yml` + 脚本）、Nginx 反代、HTTPS 预留。
- Agent 分发：平台托管安装包下载与一键安装命令。
- 文档：架构、模块、参考、运维文档体系与初始 ADR。

### Changed

- 文档结构由按开发阶段编号重构为按读者问题组织。

### Fixed

### Removed

- 移除旧阶段文档（内容迁移至新结构）。
