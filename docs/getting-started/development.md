# 开发指南

> 本文描述如何启动与开发本项目。贡献规范见 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

## 技术栈

- 后端：Python 3.11、FastAPI、SQLAlchemy 2、Pydantic 2
- 前端：Vue 3、Vite、Element Plus、Tailwind CSS v4、Pinia、ECharts
- Agent：Python 3.11（psutil、httpx）与 Go 1.24+（gopsutil、yaml.v3）双运行时
- 存储：MySQL 8、Redis 7

前端样式体系（Tailwind 与 Element Plus 的分工与层序）见 [ADR-006](../decisions/006-frontend-styling-tailwind.md)；Agent 双运行时见 [ADR-007](../decisions/007-go-agent-dual-runtime.md)。

前端样式体系（Tailwind 与 Element Plus 的分工与层序）见 [ADR-006](../decisions/006-frontend-styling-tailwind.md)。

## 本地启动

环境准备见 [local-environment.md](local-environment.md)。

```bash
# 后端（含种子数据）
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000

# 前端（/api 代理到 8000）
cd frontend
npm run dev            # http://localhost:5173
```

默认管理员：`admin` / `admin123456`（开发默认值，上线前必改）。

## 测试

```bash
# 后端
cd backend && .venv/bin/python -m pytest app/test/ -q

# Agent（Python）
agent/.venv/bin/python -m pytest agent/tests/ -q

# Agent（Go）
cd agent-go && gofmt -l . && go vet ./... && go test ./... && go build ./...

# 前端构建校验
cd frontend && npm run build
```

> Go Agent 的安装包由后端打包；本地需要预构建二进制时运行 `./deploy/build-agent-go.sh`（宿主无 Go 时自动使用 `golang` 容器）。

## 后端分层

`Router → Service → Repository → Model`，详见 [architecture/backend.md](../architecture/backend.md)。

## 相关文档

- [architecture/overview.md](../architecture/overview.md)
- [reference/api.md](../reference/api.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)
