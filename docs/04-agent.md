# Agent 协议与部署

> Agent 以 systemd 服务部署在被监控的 Linux 服务器上，不与核心容器同运行。
> 技术栈：Python 3.11、psutil、httpx。

## 一、工作流程

```text
读取配置 → 连接服务端 → Agent 注册 → 启动采集任务
→ 采集系统指标 → 数据格式化 → 发送 Metrics → 发送 Heartbeat
→ 等待下一次采集 → 循环
```

## 二、Agent 分层

| 模块 | 职责 |
| --- | --- |
| `collector/` | CPU / Memory / Disk / Network / Process / Docker 指标采集 |
| `reporter/` | Metrics 上报、Heartbeat 上报 |
| `executor/` | 受控运维命令执行（服务管理、任务） |
| `config/` | `config.yaml` 配置管理 |
| `utils/` | 日志、网络重试等工具 |

## 三、鉴权

- Agent 使用**独立 Token** 访问服务端接口，不走用户 JWT。
- Token 由服务端生成，数据库仅存 SHA-256 哈希；Agent 配置中保存明文 Token，通过 `Authorization: Bearer <token>` 头携带。
- 上报接口：`POST /api/v1/agent/register`、`/heartbeat`、`/metrics`、`/task/result`

## 四、注册

Agent 启动后先向服务端注册，服务端返回 `server_id`：

`POST /api/v1/agent/register`

```json
{
    "server_code": "web-01",
    "hostname": "web-01",
    "os_name": "Ubuntu",
    "os_version": "22.04",
    "agent_version": "1.0.0"
}
```

## 五、心跳

Agent 每 **30 秒**上报一次心跳：

`POST /api/v1/agent/heartbeat`

```json
{
    "server_id": 10001,
    "agent_version": "1.0.0",
    "timestamp": 1787300000
}
```

服务端更新 `ops_server.last_heartbeat_at` 并据此判断 Agent 状态：

| 最后心跳时间 | 状态 |
| --- | --- |
| ≤ 30 秒 | ONLINE |
| 30 < 心跳 ≤ 90 秒 | WARNING |
| > 90 秒 | OFFLINE |

## 六、指标上报

`POST /api/v1/agent/metrics`

```json
{
    "server_id": 10001,
    "timestamp": 1787300000,
    "cpu_usage": 72.3,
    "memory_usage": 61.2,
    "disk_usage": 81.4,
    "load_1m": 2.31,
    "tcp_connections": 126
}
```

服务端处理流程：Agent 身份校验 → 请求参数校验 → 数据类型校验 → 时间合法性校验 → 指标持久化 → 告警规则计算。

### 采集周期

| 指标 | 数据来源 | 采集周期 |
| --- | --- | --- |
| CPU 使用率 | psutil | 10 秒 |
| 内存使用率 | psutil | 10 秒 |
| 磁盘使用率 | psutil | 30 秒 |
| 网络流量 | psutil | 10 秒 |
| Load Average | Linux | 10 秒 |
| TCP 连接数 | Linux | 30 秒 |
| 进程信息 | psutil | 30 秒 |
| Docker 状态 | Docker | 30 秒 |

## 七、任务执行

服务端通过任务分发调用 Agent：

`POST /api/v1/agent/task/result`

Agent 执行受控命令后上报结果，字段包含：`execution_id`、`status`（SUCCESS/FAILED/TIMEOUT）、`exit_code`、`result_text`、`error_message`、`started_at`、`finished_at`。

> 安全约束：服务名称白名单校验 + 操作类型校验 + Agent 端二次校验，禁止拼接任意用户输入执行 Shell。

## 八、异常处理

### 网络异常

上报失败 → 记录本地日志 → 等待 → **指数退避重试**（如 1s/2s/4s/8s，封顶 60s）→ 连接恢复 → 继续上报。避免服务端短暂不可用导致高频请求。

### 服务异常

主进程异常退出由 systemd 自动拉起：

```ini
[Unit]
Description=Server Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/server-agent
ExecStart=/opt/server-agent/.venv/bin/python /opt/server-agent/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 九、配置示例（config/config.yaml）

```yaml
server:
  url: "http://127.0.0.1:8000"   # 服务端地址
  token: "xxxxxxxxxxxxxxxx"       # Agent 注册凭证
  server_code: "web-01"           # 服务器唯一编码

collect:
  heartbeat_interval: 30          # 心跳周期（秒）
  metrics_interval: 10            # 指标采集周期（秒）
  retry_max_seconds: 60           # 退避重试封顶（秒）

log:
  level: "INFO"
  file: "/var/log/server-agent/agent.log"
```

## 十、部署步骤

```bash
# 1. 安装依赖
cd /opt/server-agent
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 编写 config/config.yaml（服务端地址、凭证）

# 3. 安装 systemd 服务
cp deploy/systemd/server-agent.service /etc/systemd/system/

# 4. 启动并设置开机自启
systemctl daemon-reload
systemctl enable server-agent
systemctl start server-agent
systemctl status server-agent
```
