# Agent 部署

> 本文描述在被监控 Linux 服务器上安装、配置、验证与卸载 Agent。

## Scope

覆盖平台一键安装、本地 systemd 脚本与 Docker 方式；宿主指标采集与受控服务管理。

## Prerequisites

- 目标机为 Linux（Debian/Ubuntu 等），具备 systemd（systemd 方式）。
- Python 3.11+（systemd 方式）或 Docker（容器方式）。
- 目标机能访问平台地址。
- 已在平台创建服务器并取得 `server_code` 与 Token。

## Installation

### 方式零：平台一键安装（推荐）

```bash
curl -fsSL http://<平台地址>/api/v1/agent/install.sh | sudo bash -s -- \
  --url http://<平台地址> \
  --token <TOKEN> \
  --code <服务器编码> \
  --services nginx,docker,ssh
```

安装包下载：`http://<平台地址>/api/v1/agent/package`。

### 方式一：本地 systemd 脚本

```bash
cd /path/to/ops-monitor
sudo ./agent/install.sh                 # 安装到 /opt/ops-agent 并启动 server-agent
# 或：sudo ./agent/install.sh --config ./config.yaml
```

### 方式二：前台运行（调试）

```bash
cd /path/to/ops-monitor
./agent/.venv/bin/python -m agent.main
```

### 方式三：Docker（宿主指标近似）

```bash
docker build -f agent/Dockerfile -t ops-monitor-agent .
docker run -d --name ops-agent --restart unless-stopped \
  --pid=host --network=host \
  -v /proc:/host/proc:ro -v /sys:/host/sys:ro \
  -v $(pwd)/config.yaml:/app/agent/config/config.yaml:ro \
  ops-monitor-agent
```

> 容器方式默认不授予 `--privileged`，容器内无法控制宿主 systemd 服务；磁盘使用率基于容器根文件系统。生产真实监控推荐 systemd 方式。

## Configuration

`agent/config/config.yaml`：见 [reference/configuration.md](../reference/configuration.md#agent-配置agentconfigconfigyaml)。

> `server_code` 必须与平台「编码」一致，否则注册报 `401 服务器编码与凭证不匹配`。

## Registration

Agent 启动后自动注册（`POST /agent/register`），随后周期上报心跳/指标/资产/服务并轮询任务。

## Verification

```bash
systemctl status server-agent --no-pager
journalctl -u server-agent -f          # 应出现"注册成功 server_id=..."
```

平台侧：服务器状态变 `ONLINE`，详情页出现指标与服务状态。

## Upgrade

> **TODO**: 补充 Agent 升级流程（替换代码/重启服务/兼容旧配置）。

## Uninstallation

```bash
sudo systemctl disable --now server-agent
sudo rm -f /etc/systemd/system/server-agent.service
sudo rm -rf /opt/ops-agent
sudo systemctl daemon-reload
```

## Troubleshooting

见 [troubleshooting.md](troubleshooting.md#agent-issues)。

## TODO

> **TODO**: 补充 Agent 版本与协议兼容矩阵。
