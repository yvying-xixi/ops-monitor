# 本地环境

## 前置依赖

- Python 3.11+
- Node.js 18+
- MySQL 8.x、Redis 7.x（本地或容器）
- Docker / Docker Compose（部署与联调）

## 安装依赖

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp app/core/.env.example app/core/.env   # 按需修改

# Agent
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

## 数据库准备

```bash
mysql -u root -p < deploy/mysql/init/ops_monitor_schema.sql
```

## 配置

后端从环境变量读取配置（本地开发用 `backend/app/core/.env`）。完整配置项见 [reference/configuration.md](../reference/configuration.md)。

关键项：`DB_*`、`REDIS_URL`、`JWT_SECRET_KEY`、`SEED_*`。

## 启动

```bash
# 终端 1：后端
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# 终端 2：前端
cd frontend && npm run dev
```

首次启动后端会幂等初始化种子数据（角色/默认告警规则/管理员）。

## Agent 联调

1. 平台「服务器管理」创建服务器并生成 Token。
2. 配置 `agent/config/config.yaml`（url/token/server_code）后运行：
   `./agent/.venv/bin/python -m agent.main`

## 常见问题

见 [operations/troubleshooting.md](../operations/troubleshooting.md)。
