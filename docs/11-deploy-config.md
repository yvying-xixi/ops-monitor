# 平台配置化部署（Harbor 式）

> 参考 Harbor 的「配置模板 + 渲染 + 安装 + 重配置」模式：用户只编辑一个 `deploy/config.yml`，
> 用脚本完成校验、渲染、构建与启动。

## 一、快速开始

```bash
# 1. 生成并编辑配置（至少修改 hostname）
cp deploy/config.yml.tmpl deploy/config.yml
vi deploy/config.yml

# 2. 一键安装（校验 → 渲染 → 构建/拉取 → 启动 → 健康检查）
./deploy/install.sh

# 3. 修改配置后，重新渲染并重建（数据保留）
./deploy/reconfigure.sh

# 4. 部署体检（只读，不改变状态）
./deploy/check.sh
```

访问 `http://<hostname>:<http.port>`；初始管理员账号见 `config.yml`（留空则由脚本自动生成并回写）。

## 二、配置项（deploy/config.yml）

| 段 | 键 | 说明 |
| --- | --- | --- |
| - | `hostname` | 平台对外地址（访问提示与 CORS） |
| `http` | `port` | 对外 HTTP 端口（默认 80） |
| `https` | `enabled` / `port` / `certificate` / `private_key` | 启用 HTTPS（默认关闭）；证书放入 `deploy/nginx/certs` 或填路径 |
| `database` | `name` / `password` | 业务库名与密码（密码留空自动生成） |
| `redis` | `password` | Redis 密码（留空自动生成） |
| `jwt` | `secret_key` / `expire_minutes` | JWT 密钥与有效期（密钥留空自动生成） |
| `admin` | `username` / `password` | 初始管理员（仅首次 seed 生效） |
| `seed` | `init` | 启动时是否初始化种子数据 |
| `metrics` | `retention_days` | 指标保留天数 |
| `operation_log` | `enabled` | 操作审计开关 |
| `image` | `registry` / `tag` | 镜像来源；registry 为空则本地构建 |
| `data` | `volume_dir` | 数据持久化目录（宿主路径，相对 `deploy/`） |

## 三、脚本职责

| 脚本 | 作用 |
| --- | --- |
| `prepare.py` | `PyYAML` 解析 + 校验；渲染 `deploy/.env`；空密钥自动生成并**按 section 回写** `config.yml`（保留注释）；解析数据目录并创建 |
| `prepare.sh` | 渲染入口（`--check` 仅校验）；HTTPS 启用时生成 `docker-compose.https.yml` 与 `nginx/conf.d/https.conf`、拷贝证书 |
| `install.sh` | 前置检查 → 生成/读取 config.yml → prepare → `pull`（有 registry）或 `build` → 等健康 → 打印访问信息 |
| `reconfigure.sh` | `check.sh` → `prepare.sh` → `docker compose up -d`（数据保留） |
| `check.sh` | 只读体检：docker/compose/python3/PyYAML、配置校验、端口占用、数据目录可写 |

## 四、配置来源与产物

- **唯一配置源**：`deploy/config.yml`（加入 `.gitignore`，含密钥）
- **渲染产物**：`deploy/.env`（compose 通过 `--env-file deploy/.env` 读取，勿手改）
- 所有脚本以 `docker compose --env-file deploy/.env -f docker-compose.yml` 运行

## 五、HTTPS 启用

1. `config.yml` 设 `https.enabled: true`，填写 `certificate` / `private_key` 路径
2. 执行 `./deploy/prepare.sh`（或 install/reconfigure）→ 自动生成 443 配置与端口映射、拷贝证书到 `deploy/nginx/certs`
3. 重新 `up -d` 生效（`install.sh` / `reconfigure.sh` 会自动带上 HTTPS 覆盖文件）

## 六、数据与备份

- MySQL/Redis 数据落在 `data.volume_dir`（默认 `deploy/data`），备份该目录即可
- 从旧版命名卷迁移：如需保留历史数据，先 `docker cp` 或从卷导出后再切换

## 七、常见问题

| 现象 | 处理 |
| --- | --- |
| `缺少 PyYAML` | `apt install -y python3-yaml` 或 `pip install pyyaml` |
| 端口被占用 | 修改 `config.yml` 的 `http.port` 或释放端口 |
| 健康检查超时 | `docker compose --env-file deploy/.env logs -f backend` |
| 想重置数据 | 停止后清空 `data.volume_dir` 再 install（会重新 seed） |
