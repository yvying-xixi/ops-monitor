# Agent 部署指南

> 面向被监控 Linux 服务器的 Agent 部署方式：systemd（推荐）、前台调试、Docker 容器。
> 配置来源推荐使用平台前端「服务器管理 → 接入」向导生成的 `config.yaml`。

## 一、部署方式对比

| 方式 | 适用 | 宿主指标 | 服务控制 | 备注 |
| --- | --- | --- | --- | --- |
| **systemd（推荐）** | 生产、真实监控 | 完整 | 支持（需 root） | `install.sh` 一键安装 |
| 前台运行 | 调试 | 完整 | 支持 | `python -m agent.main` |
| Docker | 演示/容器环境 | 近似宿主（pid/network host） | **默认关闭** | 见限制说明 |

## 二、前置：获取配置

平台「服务器管理」→ 目标服务器「接入」向导：
1. 生成并复制 Token（明文仅一次）
2. 复制 `server_code`（**注册匹配键**，须与平台该服务器"编码"一致）
3. 编辑服务端地址与服务白名单
4. 下载 `config.yaml`

> 常见错误：把"主机名"当成 server_code 使用 → 注册报 `401 服务器编码与凭证不匹配`。

## 三、方式一：systemd 一键安装（推荐）

```bash
# 将 config.yaml 放在仓库根目录（或安装后编辑目标配置），然后：
cd /path/to/ops-monitor
sudo ./agent/install.sh                 # 默认安装到 /opt/ops-agent

# 如未提供 config.yaml，编辑后重启：
sudo vi /opt/ops-agent/agent/config/config.yaml
sudo systemctl restart server-agent

# 查看状态/日志
systemctl status server-agent --no-pager
journalctl -u server-agent -f
```

安装脚本行为：
- 复制 `agent/` 包到 `/opt/ops-agent/agent`，创建 `/opt/ops-agent/.venv`
- 安装依赖；准备 `config.yaml`（`chmod 600`）
- 安装 `deploy/systemd/server-agent.service`（`ExecStart=.../.venv/bin/python -m agent.main`，`Restart=always`）并启动

> 支持自定义目录：`sudo ./agent/install.sh /opt/custom-dir`；指定解释器：`PYTHON=python3.11 sudo -E ./agent/install.sh`

## 四、方式二：前台运行（调试）

```bash
cd /path/to/ops-monitor
./agent/.venv/bin/python -m agent.main      # 必须在仓库根执行（agent 为包）
# 或先 cd agent && PYTHONPATH=.. .venv/bin/python main.py
```

## 五、方式三：Docker 容器

构建与运行见 `agent/Dockerfile` 顶部注释，简述：

```bash
docker build -f agent/Dockerfile -t ops-monitor-agent:latest .
docker run -d --name ops-agent --restart unless-stopped \
  --pid=host --network=host \
  -v /proc:/host/proc:ro -v /sys:/host/sys:ro \
  -v $(pwd)/config.yaml:/app/agent/config/config.yaml:ro \
  ops-monitor-agent:latest
```

**限制与安全**：
- `--pid=host` + `--network=host` 使 CPU/内存/Load/TCP/网络计数贴近宿主；`/proc`、`/sys` 只读挂载供后续扩展
- **磁盘使用率基于容器根文件系统**，非宿主（如需宿主磁盘需扩展代码路径）
- **默认不授予 `--privileged`**，容器内无法控制宿主 systemd 服务（服务状态读取也可能受限）；如需容器内服务管理，仅在容器内部有意义
- 容器化主要用于演示/容器环境；**生产真实监控推荐 systemd 方式**

## 六、配置项（config.yaml）

| 段 | 键 | 说明 |
| --- | --- | --- |
| server | url / token / server_code | 服务端地址、注册凭证、编码（匹配键） |
| collect | heartbeat_interval | 心跳周期（秒，默认 30） |
| collect | metrics_interval | 指标周期（秒，默认 10） |
| collect | assets_interval | 资产/服务同步周期（秒，默认 60） |
| collect | task_poll_interval | 任务轮询周期（秒，默认 5） |
| collect | services | 监控与受控服务白名单 |
| log | level / file | 日志级别与文件 |

## 七、故障排查

| 现象 | 处理 |
| --- | --- |
| `401 服务器编码与凭证不匹配` | `server_code` 与平台"编码"不一致，或 Token 属于其他服务器 |
| `401 Agent 凭证无效` | Token 错误/已撤销/已过期，重新生成 |
| `ModuleNotFoundError: No module named 'agent'` | 需在仓库根用 `python -m agent.main`，或 `PYTHONPATH=.. python main.py` |
| 服务状态 UNKNOWN / 控制失败 | 目标机无 systemd、无该服务或权限不足（`systemctl is-active <svc>` 自查） |
| 状态一直 OFFLINE | 检查服务端地址可达、心跳周期、后端 `/api/v1/health` |
