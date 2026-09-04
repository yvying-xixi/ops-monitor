# 轻量级服务器运维监控平台

面向 Linux 服务器的**轻量级运维监控与自动化管理平台**。通过 Python Agent 采集服务器运行状态，由 FastAPI 后端统一接收、处理和存储监控数据，并经 Vue 管理端提供可视化监控、服务器管理、服务管理、告警管理及自动化任务能力。

## 核心能力

- **服务器资产管理**：服务器注册、Agent 凭证、在线状态（心跳判定）、资产详情
- **服务器监控**：CPU / 内存 / 磁盘 / 网络 / Load / TCP 连接 / 进程 / Docker 容器
- **可视化 Dashboard**：实时指标、历史趋势（ECharts）
- **告警中心**：阈值规则、WARNING / CRITICAL 分级、事件确认与恢复
- **服务管理**：Nginx / Docker / SSH 等受控服务的状态查询、启动、停止、重启、日志
- **自动化任务**：单机 / 批量 / 定时任务，执行记录与日志
- **用户权限**：JWT 身份认证、RBAC 角色权限、操作审计

## 技术栈

| 端 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite 6、Element Plus 2、Pinia、Vue Router 4、Axios、ECharts 5 |
| 后端 | Python 3.11、FastAPI、SQLAlchemy 2、Pydantic 2、PyJWT、APScheduler |
| Agent | Python 3.11、psutil、httpx |
| 存储 | MySQL 8、Redis 7 |
| 部署 | Docker / Docker Compose、Nginx、systemd（Agent） |

## 目录结构

```text
ops-monitor/
├── backend/            # FastAPI 后端
│   └── app/
│       ├── api/v1/     # 路由：auth/users/servers/metrics/alerts/services/tasks
│       ├── models/     # SQLAlchemy ORM 模型
│       ├── schemas/    # Pydantic 请求/响应模型
│       ├── services/   # 业务逻辑
│       ├── repositories/ # 数据访问
│       ├── core/       # 配置、安全、数据库、日志
│       ├── middleware/ # 中间件
│       ├── exceptions/ # 统一异常
│       ├── utils/      # 工具类
│       └── main.py     # 应用入口
├── agent/              # Linux 监控 Agent
│   ├── collector/      # 指标采集（cpu/memory/disk/network/process/docker）
│   ├── reporter/       # 上报（metrics/heartbeat）
│   ├── executor/       # 受控命令执行
│   ├── config/         # config.yaml 配置
│   ├── utils/
│   └── main.py
├── frontend/           # Vue 管理端
│   └── src/
│       ├── api/        # 接口封装
│       ├── views/      # 页面
│       ├── components/ # 组件
│       ├── router/     # 路由
│       ├── store/      # 状态管理
│       ├── utils/
│       └── config/
├── deploy/             # Docker / Nginx 部署配置
├── sql/                # 数据库建表脚本
├── docs/               # 开发文档
└── docker-compose.yml  # 容器编排
```

## 快速启动

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 按需修改环境变量
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173（/api 已代理到后端 8000）
```

> 开发环境先启动后端（含种子数据），默认管理员：`admin` / `admin123456`（上线前必改）。

### Agent

1. 管理员先在后端创建服务器并生成注册凭证：
   `POST /api/v1/servers` → `POST /api/v1/servers/{id}/agent-token`（Token 明文仅返回一次）
2. 配置并启动 Agent：

```bash
cd agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config/config.yaml.example config/config.yaml   # 填入服务端地址、token、server_code
python main.py
```

生产环境建议以 systemd 服务部署：`/etc/systemd/system/server-agent.service`。

### 数据库初始化

```bash
mysql -u root -p < sql/ops_monitor_schema.sql
```

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `DB_HOST` | MySQL 地址 | `127.0.0.1` |
| `DB_PORT` | MySQL 端口 | `3306` |
| `DB_USER` | MySQL 用户名 | `root` |
| `DB_PASSWORD` | MySQL 密码 | - |
| `DB_NAME` | 数据库名 | `ops_monitor` |
| `REDIS_URL` | Redis 连接串（本地开发用 `127.0.0.1`；容器部署由 Compose 注入服务名 `redis`） | `redis://127.0.0.1:6379/0` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | - |
| `JWT_EXPIRE_MINUTES` | Token 有效期（分钟） | `120` |
| `AGENT_SERVER_URL` | Agent 上报服务端地址 | `http://127.0.0.1:8000` |

## Docker Compose 部署

```bash
cp .env.example .env          # 修改 DB/REDIS 密码、JWT、种子管理员
docker compose up -d --build  # 构建并启动（首启自动建表 + seed）
docker compose ps             # 全部 healthy 后访问 http://<host>:80
docker compose logs -f backend   # 查看日志
docker compose down           # 停止（保留数据卷）
docker compose down -v        # 停止并清理数据卷
```

- 服务：`nginx`（静态 + `/api` 反代，暴露 `HTTP_PORT`）、`backend`、`mysql`、`redis`
- 详见 [docs/09-phase7-deploy.md](docs/09-phase7-deploy.md)

## 端口约定

| 服务 | 端口 |
| --- | --- |
| 后端 FastAPI | `8000` |
| 前端 Vite Dev | `5173` |
| MySQL | `3306` |
| Redis | `6379` |
| Nginx（容器内） | `80` |

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [docs/01-overview.md](docs/01-overview.md) | 项目背景、功能架构、角色权限、分层架构 |
| [docs/02-database.md](docs/02-database.md) | 数据库设计：26 张表、索引、常用查询 |
| [docs/03-development.md](docs/03-development.md) | 开发规范：分层约定、响应格式、日志、提交规范 |
| [docs/04-agent.md](docs/04-agent.md) | Agent 协议：注册、心跳、指标上报、部署 |
| [docs/05-phase2-auth.md](docs/05-phase2-auth.md) | 阶段二用户权限模块设计：决策、错误码、接口、实现要点 |
| [docs/06-phase4-monitor.md](docs/06-phase4-monitor.md) | 阶段四监控中心：指标查询/聚合差分、Dashboard、前端结构 |
| [docs/07-phase5-alert.md](docs/07-phase5-alert.md) | 阶段五告警中心：告警引擎、状态机、默认规则、接口 |
| [docs/08-phase6-task.md](docs/08-phase6-task.md) | 阶段六自动化运维：任务引擎、服务管理、安全约束、接口 |
| [docs/09-phase7-deploy.md](docs/09-phase7-deploy.md) | 阶段七部署优化：镜像/Compose/Nginx/CI、启动与上线清单 |

## 开发进度

- [x] 阶段一 · 基础设置：Git 仓库、依赖安装、目录骨架、数据库脚本
- [x] 阶段一 · 数据映射：26 张表 SQLAlchemy ORM、泛型仓储 + 用户权限域仓储
- [x] 阶段二 · 用户权限（前后端闭环）：登录/JWT/用户管理/RBAC/操作审计
  - [x] M1 基础能力层：安全工具、统一异常、统一响应
  - [x] M2 登录闭环：登录接口、用户管理 API、种子数据、Health
  - [x] M3 鉴权与审计：鉴权依赖、操作日志中间件、接口权限
  - [x] M4 前端用户权限：登录页/守卫/角色菜单、刷新会话恢复
- [x] 阶段三 · Agent：指标采集、注册、心跳、上报、资产同步、状态刷新
  - [x] 服务端：`/agent/register|heartbeat|metrics|assets` + 服务器管理 + APScheduler 状态判定
  - [x] Agent 客户端：CPU/Memory/Disk/Network/Load/TCP/Uptime 采集 + 上报重试
  - [x] E2E 全链路验证
- [x] 阶段四 · 监控中心：服务器详情指标查询、Dashboard、ECharts 图表
  - [x] 后端：metrics latest/history/summary（分桶聚合 + 网络速率差分）、dashboard overview、auth/me、roles
  - [x] 前端：登录/布局/路由守卫、Dashboard、服务器列表与详情、用户管理
- [x] 阶段五 · 告警中心：规则、事件、确认、恢复
  - [x] 告警引擎：定时评估、PENDING→FIRING→ACKNOWLEDGED→RESOLVED、去重、恢复自动解除
  - [x] 接口：事件列表/详情/确认/恢复、规则 CRUD；Dashboard 实时告警卡片
  - [x] 前端：告警中心（事件 + 规则管理）
- [x] 阶段六 · 自动化运维：服务管理、批量任务、任务日志
  - [x] 服务状态采集上报 + 白名单控制
  - [x] 任务引擎：创建/确认/取消/领取/回传/超时/状态聚合；单机/批量/定时
  - [x] Agent 受控执行器（白名单+禁 shell）；任务中心与服务管理前端
- [x] 阶段七 · 部署优化：镜像、Compose、Nginx、CI
  - [x] backend/nginx 镜像、docker-compose 编排、Nginx 反代、CI workflow、部署文档
