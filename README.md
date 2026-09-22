# Ops Monitor

轻量级服务器运维监控与自动化管理平台：通过 Python Agent 采集 Linux 服务器状态，由 FastAPI 后端统一处理，经 Vue 管理端提供监控、告警与服务管理能力。

## Features

- 服务器资产管理与 Agent 在线状态
- 指标采集与可视化（CPU / 内存 / 磁盘 / 网络 / Load / TCP / 进程）
- 阈值告警（规则、事件、确认、恢复）
- 服务管理（状态监控、受控启停、日志）
- 自动化任务（单机 / 批量 / 定时、执行记录）
- 用户认证与 RBAC 权限、操作审计
- Docker Compose 配置化部署

## Architecture

```text
浏览器 → Nginx → Vue 前端 / FastAPI 后端 → MySQL / Redis
                                      ▲
                         Linux Agent（主动上报/轮询）
```

详见 [docs/architecture/overview.md](docs/architecture/overview.md)。

## Quick Start

```bash
# 平台（配置化部署）
cp deploy/config.yml.tmpl deploy/config.yml   # 编辑 hostname/端口/密码
./deploy/install.sh
```

详见 [docs/operations/deployment.md](docs/operations/deployment.md)。

## Documentation

- [Getting Started](docs/getting-started/)
- [Architecture](docs/architecture/)
- [Modules](docs/modules/)
- [Reference](docs/reference/)
- [Operations](docs/operations/)
- [Architecture Decisions](docs/decisions/)

## Development

- [开发指南](docs/getting-started/development.md)
- [本地环境](docs/getting-started/local-environment.md)
- [贡献指南](CONTRIBUTING.md)

## Deployment

- [平台部署](docs/operations/deployment.md)
- [Agent 部署](docs/operations/agent-deployment.md)

## License

许可证待定，见 [依赖许可证清单](docs/reference/license-inventory.md)。
