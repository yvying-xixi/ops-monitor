# 阶段七 · 部署优化

> 对应总体规划「七、部署优化」：Docker 镜像、Compose、Nginx、HTTPS、CI/CD。
> 文档固化容器化部署方式与验证结论。

## 一、容器组成

```
Internet → Nginx(HTTP_PORT:80)
             ├── / 前端静态资源（Vue dist）
             └── /api/* → backend:8000（uvicorn，2 worker）
backend ── mysql:8.0（仅内网）
backend ── redis:7（仅内网）
```

- **单 Nginx 入口**：镜像多阶段（node 构建前端 → nginx:alpine 托管），同时承担静态与 `/api` 反代
- backend 独立镜像：`python:3.11-slim`、非 root、HEALTHCHECK、环境变量注入配置
- mysql/redis 不暴露宿主端口，named volume 持久化 + healthcheck
- `./sql` 首启挂载自动建表；lifespan 幂等 seed 默认角色/规则/管理员

## 二、启动方式

```bash
# 准备环境变量
cp .env.example .env        # 修改 DB/REDIS 密码、JWT、种子管理员、HTTP_PORT

# 构建并启动
docker compose up -d --build
docker compose ps           # 全部 healthy
docker compose logs -f backend

# 停止/清理
docker compose down         # 保留数据卷
docker compose down -v      # 连同数据卷一起清理
```

访问 `http://<host>:${HTTP_PORT}`，默认管理员见 `.env` 中 `SEED_ADMIN_*`。

## 三、Nginx 配置

- `location /api/` → `proxy_pass http://backend:8000`（Host/X-Forwarded-For/X-Request-ID 透传）
- `location /` → SPA history 路由回退到 `index.html`
- 静态资源缓存、gzip
- **HTTPS 预留**：`deploy/nginx/conf.d/default.conf` 内含注释的 `443` server 段与 HTTP→HTTPS 跳转；
  证书放入 `deploy/nginx/certs/`（fullchain.pem/privkey.pem）后取消注释并重载 nginx

## 四、CI/CD

`.github/workflows/ci.yml`（push/PR → master）：
- **backend**：services mysql:8.0 + redis:7 → pip install → 建表引导 → `pytest app/test/`
- **agent**：pip install → `pytest agent/tests/`
- **frontend**：npm ci → build

> 说明：仓库当前远端为 SSH 别名，workflow 按标准 GitHub Actions 编写入库，接入真实 GitHub 仓库后即生效。

## 五、Agent 部署（生产）

Agent 不以核心容器运行，以 systemd 部署于被监控服务器：

```bash
cd /opt/server-agent && python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp agent/config/config.yaml.example agent/config/config.yaml   # 服务端地址 + server_code + token
# 安装 /etc/systemd/system/server-agent.service（Restart=always）
systemctl enable --now server-agent
```

## 六、验证结论（本地冒烟）

- `docker compose up -d --build`：mysql/redis/backend/nginx 全部 healthy
- 经 Nginx `8090`：登录 seed admin ✅、`/api/v1/health` ✅、前端首页 200 ✅
- 全链路：创建服务器 → 生成 Agent 凭证 → 真实 Agent 注册/上报指标（经 Nginx 反代）→ `ONLINE=1`、avg_cpu 有值 ✅
- 冒烟后 `down -v` 清理

## 七、上线安全清单

- 修改 `JWT_SECRET_KEY` 与 DB/REDIS 密码（`.env`，不入库）
- 修改/移除种子管理员默认密码，或用独立初始化流程创建
- 正式环境启用 HTTPS（certs 就位 + 443 段）
- 操作审计、命令白名单、Agent Token 哈希已内置，无需额外开关
