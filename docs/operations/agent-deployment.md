# Agent 部署

> 本文描述在被监控 Linux 服务器上安装、配置、验证与卸载 Agent。

## 范围

覆盖平台一键安装、本地 systemd 脚本与前台运行；宿主指标采集与受控服务管理。

## 前置条件

- 目标机为 Linux（Debian/Ubuntu 等），具备 systemd（systemd 方式）。
- 目标机能访问平台地址。
- 已在平台创建服务器并取得 `server_code` 与 Token。
- 运行时依赖：
  - Python 版：Python 3.11+（systemd / 前台方式）。
  - Go 版：无外部运行时（静态单二进制）。

## 安装

### 方式零：平台一键安装（推荐）

Python 版（默认）：

```bash
curl -fsSL http://<平台地址>/api/v1/agent/install.sh | sudo bash -s -- \
  --url http://<平台地址> \
  --token <TOKEN> \
  --code <服务器编码> \
  --services nginx,docker,ssh
```

Go 版（单二进制，免 Python 运行时）：

```bash
curl -fsSL http://<平台地址>/api/v1/agent/install.sh?runtime=go | sudo bash -s -- \
  --url http://<平台地址> \
  --token <TOKEN> \
  --code <服务器编码> \
  --services nginx,docker,ssh
```

安装包下载：`http://<平台地址>/api/v1/agent/package[?runtime=go]`。

> Go 版安装脚本会按 `uname -m` 选择 amd64/arm64 二进制；包内 `dist/` 需已包含对应架构产物（由 `deploy/build-agent-go.sh` 或 Release 提供）。
>
> 预编译二进制与 tar.gz 安装包由 GitHub Release 提供，tag 形如 `agent-vX.Y.Z`（如 `agent-v1.0.0`），含 linux/amd64、arm64 与 `ops-agent-go-<version>.tar.gz`。

```mermaid
flowchart LR
    A[平台创建服务器/生成 Token] --> B[生成 config.yaml]
    B --> C[目标机执行一键命令/脚本]
    C --> D[复制 agent 包/二进制 + 建 venv 或安装二进制]
    D --> E[写入 config.yaml]
    E --> F[安装并启动 server-agent]
    F --> G[自动注册 → ONLINE]
```

### 方式一：本地 systemd 脚本

```bash
cd /path/to/ops-monitor

# Python 版
sudo ./agent/install.sh                 # 安装到 /opt/ops-agent 并启动 server-agent
# 或：sudo ./agent/install.sh --config ./config.yaml

# Go 版（需先构建二进制）
./deploy/build-agent-go.sh
sudo ./agent-go/install.sh              # 或：sudo ./agent-go/install.sh --config ./config.yaml
```

### 方式二：前台运行（调试）

```bash
cd /path/to/ops-monitor

# Python 版
./agent/.venv/bin/python -m agent.main

# Go 版（安装后）
sudo /opt/ops-agent/bin/ops-agent --config /opt/ops-agent/config/config.yaml
# 或直接运行构建产物
./agent-go/dist/ops-agent-linux-amd64 --config /path/to/config.yaml
```

## 配置

Python 与 Go 版使用同一份 `config.yaml`：见 [reference/configuration.md](../reference/configuration.md#agent-配置python-与-go-通用)。

> `server_code` 必须与平台「编码」一致，否则注册报 `401 服务器编码与凭证不匹配`。

## 注册

Agent 启动后自动注册（`POST /agent/register`），随后周期上报心跳/指标/资产/服务并轮询任务。

## 验证

```bash
systemctl status server-agent --no-pager
journalctl -u server-agent -f          # 应出现"注册成功 server_id=..."
```

平台侧：服务器状态变 `ONLINE`，详情页出现指标与服务状态。

## 服务器发现（只读）

批量接入前可先在**授权网段**内做只读探测（[ADR-012](../decisions/012-read-only-server-discovery.md)）。

在 `config.env` 配置白名单并开启：

```text
DISCOVERY_ENABLED=true
DISCOVERY_ALLOWED_CIDRS=["10.0.0.0/24"]
```

然后在管理端「服务器发现」页输入网段扫描（或调用 `POST /api/v1/discovery/scan`，仅 `SYSTEM_ADMIN`）；对探测到的主机，人工通过「添加服务器 + Agent 向导」接入。

限制：仅扫描白名单子网；只做 TCP/banner 探测，**不认证、不远程安装**。

## 升级

见 [upgrade.md](upgrade.md#agent-升级)：保留 `config.yaml` 与签名私钥，替换程序后重启 `server-agent`。

## 卸载

```bash
sudo systemctl disable --now server-agent
sudo rm -f /etc/systemd/system/server-agent.service
sudo rm -rf /opt/ops-agent
sudo systemctl daemon-reload
```

## 请求签名密钥

- 首次运行自动生成 Ed25519 私钥（`agent_ed25519.key`，权限 0600），路径由 `server.signing_key_file` 指定（默认相对 `config.yaml` 目录解析）。
- 注册时上报公钥；平台在 `AGENT_REQUIRE_SIGNATURE=true` 后强制验签。
- 重新部署时**保留**该私钥文件；删除后会生成新密钥并重新注册（旧公钥失效）。

## 故障排查

见 [troubleshooting.md](troubleshooting.md#agent-问题)。

## 待办

- [x] Agent 版本与协议兼容矩阵：见 [agent-protocol.md](../reference/agent-protocol.md#兼容性)。
