# 端口 Reference

## 平台服务端口

| 服务 | 容器端口 | 宿主端口 | 说明 |
| --- | ---: | --- | --- |
| Nginx（入口） | 80 | `HTTP_PORT`（默认 80） | 静态资源 + `/api` 反代 |
| Nginx（HTTPS） | 443 | `HTTPS_PORT`（默认 443） | 启用 HTTPS 时 |
| Backend（uvicorn） | 8000 | 仅内网 | 经 Nginx 反代访问 |
| MySQL | 3306 | 仅内网 | 不暴露宿主 |
| Redis | 6379 | 仅内网 | 不暴露宿主 |

> Compose 中 `mysql`/`redis` 不映射宿主端口，仅在 `ops-net` 内网访问。

## 本地开发端口

| 服务 | 端口 | 说明 |
| --- | ---: | --- |
| Backend（uvicorn dev） | 8000 | `uvicorn app.main:app` |
| Frontend（Vite dev） | 5173 | `/api` 代理到 `127.0.0.1:8000` |
| MySQL（本地） | 3306 | 需本地可达 |
| Redis（本地） | 6379 | 需本地可达 |

## Agent

Agent 不监听端口，仅主动出站访问平台地址（`server.url`）。
