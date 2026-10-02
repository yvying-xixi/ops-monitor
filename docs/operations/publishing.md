# 镜像发布

> 本文描述 `ops-monitor` 两个容器镜像的构建与发布：Docker Hub 由 CI 推送，Harbor（内网）由本地脚本推送。

## 镜像清单

| 镜像 | 用途 | 构建上下文 | Dockerfile |
| --- | --- | --- | --- |
| `ops-monitor-backend` | FastAPI 后端 API | `backend/` | `deploy/docker/Dockerfile.backend` |
| `ops-monitor-frontend` | 前端静态资源 + Nginx 入口 | 仓库根目录 | `deploy/nginx/Dockerfile` |

- 平台仅 `linux/amd64`。
- Agent 不打包镜像（以 systemd 原生部署）。
- 版本来源：仓库根 `VERSION`；发布时打 git tag `vX.Y.Z`，镜像同时带 `vX.Y.Z` 与 `latest`。

## Docker Hub（GitHub Actions）

工作流：`.github/workflows/publish.yml`。

触发方式：

- 推送 tag：`git push origin v0.2.0` 自动触发。
- 手动触发（`workflow_dispatch`，可填发布 tag）。

流程：先复用 `.github/workflows/ci.yml` 跑测试，全部通过后再 buildx 构建并推送。

需在仓库 Settings → Secrets and variables → Actions 配置：

| Secret | 说明 |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub 用户名/组织（同时作为镜像命名空间） |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token（Read & Write） |

推送结果（公开仓库）：

```text
docker.io/<DOCKERHUB_USERNAME>/ops-monitor-backend:vX.Y.Z
docker.io/<DOCKERHUB_USERNAME>/ops-monitor-backend:latest
docker.io/<DOCKERHUB_USERNAME>/ops-monitor-frontend:vX.Y.Z
docker.io/<DOCKERHUB_USERNAME>/ops-monitor-frontend:latest
```

## Harbor（本地脚本）

脚本：`deploy/publish.sh`。适用于仅内网可达的 Harbor（HTTP registry）。

前置条件：

1. 已在 Harbor 创建项目（默认 `ops-monitor`）。
2. 已将 Harbor 主机加入 Docker 的 `insecure-registries` 并重启 docker：

```bash
sudoedit /etc/docker/daemon.json
# 在 insecure-registries 数组中加入 "192.168.10.24"
sudo systemctl restart docker
docker info | grep -A2 'Insecure Registries'
```

用法（凭据仅通过环境变量传入，不落盘）：

```bash
HARBOR_USERNAME='<机器人账号名>' HARBOR_PASSWORD='<令牌>' ./deploy/publish.sh 0.2.0
```

可选环境变量：`HARBOR_REGISTRY`（默认 `192.168.10.24`）、`HARBOR_PROJECT`（默认 `ops-monitor`）、`PLATFORM`（默认 `linux/amd64`）。

推送结果：

```text
192.168.10.24/ops-monitor/ops-monitor-backend:v0.2.0 与 :latest
192.168.10.24/ops-monitor/ops-monitor-frontend:v0.2.0 与 :latest
```

## 版本发布流程

```bash
# 1. 更新版本与变更日志
#    修改 VERSION、CHANGELOG.md
# 2. 提交并推送
git add VERSION CHANGELOG.md
git commit -m "chore(release): v0.2.0"
git push origin master
# 3. 打 tag 触发 Docker Hub 发布
git tag v0.2.0
git push origin v0.2.0
# 4. 本地推送 Harbor
HARBOR_USERNAME='<机器人账号名>' HARBOR_PASSWORD='<令牌>' ./deploy/publish.sh 0.2.0
```

## 从 Harbor 部署

```bash
IMAGE_REGISTRY=192.168.10.24/ops-monitor IMAGE_TAG=v0.2.0 ./deploy/install.sh
```

`deploy/prepare.sh` 会据此派生 `BACKEND_IMAGE` / `NGINX_IMAGE` 写入 `deploy/.env`，`install.sh` 检测到 `IMAGE_REGISTRY` 非空时改为 `docker compose pull`。

## 故障排查

| 现象 | 处理 |
| --- | --- |
| `http: server gave HTTP response to HTTPS client` | Harbor 未加入 `insecure-registries`，按上文修改 `daemon.json` 并重启 docker |
| `denied: requested access to the resource is denied` | Harbor/Docker Hub 账号或项目权限不足；确认机器人账号有 push 权限 |
| Docker Hub 发布未触发 | 确认 tag 形如 `v*` 且已推送；`upstream` 工作流 `Publish Images` 是否运行 |
| 发布工作流在 tests 阶段失败 | 先修复 CI（见 [ci.yml](../../.github/workflows/ci.yml)），再重新打 tag |

## 相关文档

- [operations/deployment.md](deployment.md)
- [reference/configuration.md](../reference/configuration.md)
