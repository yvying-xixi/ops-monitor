# Agent 部署指南

> 面向被监控 Linux 服务器的 Agent 部署方式：systemd（推荐）、前台调试、Docker 容器。
> 配置来源推荐使用平台前端「服务器管理 → 接入」向导生成的 `config.yaml`。

## 一、部署方式对比

| 方式 | 适用 | 宿主指标 | 服务控制 | 备注 |
| --- | --- | --- | --- | --- |
| **平台一键（推荐）** | 生产、真实监控 | 完整 | 支持（需 root） | 向导生成命令，一键安装 |
| systemd 本地 | 生产、离线 | 完整 | 支持（需 root） | `install.sh` 一键安装 |
| 前台运行 | 调试 | 完整 | 支持 | `python -m agent.main` |
| Docker | 演示/容器环境 | 近似宿主（pid/network host） | **默认关闭** | 见限制说明 |

## 二、前置：获取配置

平台「服务器管理」→ 目标服务器「接入」向导：
1. 生成并复制 Token（明文仅一次）
2. 复制 `server_code`（**注册匹配键**，须与平台该服务器"编码"一致）
3. 编辑服务端地址与服务白名单
4. 下载 `config.yaml`

> 常见错误：把"主机名"当成 server_code 使用 → 注册报 `401 服务器编码与凭证不匹配`。

## 三、方式零：平台一键安装（推荐）

平台提供安装包与安装脚本，向导会生成一条命令，在目标机执行即可完成安装与注册：

```bash
curl -fsSL http://<平台地址>/api/v1/agent/install.sh | sudo bash -s -- \
  --url http://<平台地址> \
  --token <向导复制的 Token> \
  --code <服务器编码> \
  --services nginx,docker,ssh
```

- 安装包下载：`http://<平台地址>/api/v1/agent/package`（tar.gz，含源码 + install.sh + systemd 模板）
- 也可在前端「服务器管理 → 接入」向导中点击「下载 Agent 包」或复制上面的命令
- 脚本会：复制 agent 包 → 建 venv 装依赖 → 按参数生成 `config.yaml` → 安装并启动 systemd 服务

## 四、方式一：systemd 本地安装

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

> 自定义目录：`sudo ./agent/install.sh --dir /opt/custom-dir`；指定解释器：`PYTHON=python3.11 sudo -E ./agent/install.sh`；也可 `--url/--token/--code/--services` 直接生成配置

## 五、方式二：前台运行（调试）

```bash
cd /path/to/ops-monitor
./agent/.venv/bin/python -m agent.main      # 必须在仓库根执行（agent 为包）
# 或先 cd agent && PYTHONPATH=.. .venv/bin/python main.py
```

## 六、方式三：Docker 容器

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

## 七、配置项（config.yaml）

| 段 | 键 | 说明 |
| --- | --- | --- |
| server | url / token / server_code | 服务端地址、注册凭证、编码（匹配键） |
| collect | heartbeat_interval | 心跳周期（秒，默认 30） |
| collect | metrics_interval | 指标周期（秒，默认 10） |
| collect | assets_interval | 资产/服务同步周期（秒，默认 60） |
| collect | task_poll_interval | 任务轮询周期（秒，默认 5） |
| collect | services | 监控与受控服务白名单 |
| log | level / file | 日志级别与文件 |

## 八、故障排查

| 现象 | 处理 |
| --- | --- |
| `401 服务器编码与凭证不匹配` | `server_code` 与平台"编码"不一致，或 Token 属于其他服务器 |
| `401 Agent 凭证无效` | Token 错误/已撤销/已过期，重新生成 |
| `ModuleNotFoundError: No module named 'agent'` | 需在仓库根用 `python -m agent.main`，或 `PYTHONPATH=.. python main.py` |
| 服务状态 UNKNOWN / 控制失败 | 目标机无 systemd、无该服务或权限不足（`systemctl is-active <svc>` 自查） |
| 状态一直 OFFLINE | 检查服务端地址可达、心跳周期、后端 `/api/v1/health` |

## 九、排错经验（真实案例）

### 案例 1：注册报 `401 服务器编码与凭证不匹配`

- **症状**：Agent 反复重试注册，日志 `POST /api/v1/agent/register 返回 401: 服务器编码与凭证不匹配`
- **根因**：`config.yaml` 的 `server_code` 填成了**主机名**（如 `web-01`），而平台注册匹配键是服务器的**编码**（如 `debian13`）。Token 本身有效（能通过鉴权），只是编码对不上。
- **定位**：
  ```bash
  # 查看平台侧该 Token 绑定的服务器编码
  docker exec <mysql容器> mysql -uroot -p<pwd> ops_monitor \
    -e "SELECT id,server_code FROM ops_server; SELECT server_id,token_prefix FROM ops_agent_token;"
  ```
- **处置**：把 `config.yaml` 的 `server_code` 改为平台「服务器管理」列表里该服务器的**编码**列值。
- **预防**：使用前端「服务器管理 → 接入」向导**复制** `server_code`，不要手抄；`server_code` 是唯一匹配键，主机名仅展示。

### 案例 2：`python main.py` 报 `No module named 'agent'`

- **症状**：`cd agent && python main.py` 报 `ModuleNotFoundError: No module named 'agent'`
- **根因**：Agent 采用**包式绝对导入**（`from agent.collector import ...`）。直接运行脚本时 Python 把**脚本所在目录**（`agent/`）加入 `sys.path`，而 `agent` 包位于其父目录（仓库根），因此找不到。
- **处置**：在仓库根以模块方式运行
  ```bash
  ./agent/.venv/bin/python -m agent.main          # 推荐
  # 或： cd agent && PYTHONPATH=.. .venv/bin/python main.py
  ```
- **预防**：`agent/install.sh` 与 systemd 单元统一使用 `-m agent.main` + `WorkingDirectory=部署根`。

### 案例 3：前端看不到「下载 config.yaml」/ 新功能

- **症状**：文档提到前端可下载 `config.yaml`，但页面上没有该按钮
- **根因**：① 该功能在**未合并的分支**上；② 即使已合并，运行中的前端镜像是**旧构建**（静态资源未重建）
- **处置**：
  ```bash
  git merge <功能分支>            # 先合并
  docker compose up -d --build nginx   # 再重建前端镜像
  ```
  开发模式则重启 `npm run dev`。
- **预防**：改前端后必须重建镜像或重启 dev server；功能开发完及时合并到主分支，避免"代码在、环境无"。

