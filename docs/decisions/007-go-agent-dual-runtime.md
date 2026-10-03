# ADR-007: 新增 Go 版 Agent（与 Python 双运行时并存）

## 状态

Accepted

## 背景

Agent 部署在被监控 Linux 服务器上，此前为 Python 实现，需要目标机安装 Python 3.11+ 并创建 venv。这带来若干限制：

- 目标机需预装 Python 运行时与编译依赖（psutil）。
- 分发为源码包，安装依赖网络与 pip。
- 离线或精简系统上部署成本较高。

为降低部署门槛并提升分发效率，决定引入 Go 版 Agent。Go 可编译为无外部依赖的静态单二进制，交叉编译方便、启动快、资源占用低。

## 决策

新增 `agent-go/`，与现有 `agent/`（Python）**双运行时并存**：

- 两者实现**同一份协议**（`docs/reference/agent-protocol.md`），功能对等：注册、心跳、指标/资产/服务上报、任务轮询与受控执行、日志抓取。
- 两者共用**同一份 `config.yaml` schema**，可复用平台向导生成的配置。
- Go Agent 使用 `gopsutil/v4` 采集、`log/slog` 记录、标准库 `net/http` 通信；`CGO_ENABLED=0` 静态编译。
- 平台按 `runtime` 参数（`python` 默认 / `go`）打包与分发：`/api/v1/agent/package?runtime=` 与 `/api/v1/agent/install.sh?runtime=`。
- Go 二进制由 `deploy/build-agent-go.sh` 预构建到 `agent-go/dist/`（宿主无 Go 时用 `golang` 容器），随镜像/部署分发；发布流程亦产出 GitHub Release 二进制。
- 前端接入向导默认 Python，可选 Go。

## 备选方案

### 完全用 Go 替换 Python

- 优点：单一实现，维护面收敛。
- 缺点：破坏现有后端 E2E 测试对 Python 采集器/上报器的直接引用，改动面大、风险高；迁移期无法灰度。

### 维持 Python，仅优化打包（如 PyInstaller）

- 优点：不新增技术栈。
- 缺点：产物体积大、跨发行版兼容差，仍需在目标机处理动态库。

### Go 仅作独立发行，不改平台

- 优点：平台零改动。
- 缺点：无法通过平台向导一键安装，用户体验割裂。

## 影响

### 正面

- Go 单二进制免运行时，目标机无需 Python 与 pip，离线可部署。
- 交叉编译与静态链接便于多架构分发（amd64/arm64）。
- 协议与配置 schema 复用，平台与前端无需为两者分别适配。

### 负面

- 需长期维护两套实现，协议变更须同步两处（以协议文档为契约）。
- 两实现的采集细节可能存在细微差异（如服务状态映射、磁盘分区语义），需以测试与文档约束。
- CI 需新增 Go 作业与交叉编译发布流程。
