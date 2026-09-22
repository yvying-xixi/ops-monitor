# 开发指南

> 本文描述如何启动与开发本项目。贡献规范见 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

## 技术栈

- 后端：Python 3.11、FastAPI、SQLAlchemy 2、Pydantic 2
- 前端：Vue 3、Vite、Element Plus、Pinia、ECharts
- Agent：Python 3.11、psutil、httpx
- 存储：MySQL 8、Redis 7

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

# Agent
agent/.venv/bin/python -m pytest agent/tests/ -q

# 前端构建校验
cd frontend && npm run build
```

## 后端分层

`Router → Service → Repository → Model`，详见 [architecture/backend.md](../architecture/backend.md)。

## 相关文档

- [architecture/overview.md](../architecture/overview.md)
- [reference/api.md](../reference/api.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md)
