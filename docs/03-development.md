# 开发规范

## 一、环境准备

- Python 3.11+（后端与 Agent 分别使用独立 `.venv`）
- Node.js（前端，Vite 6 要求 Node 18+）
- MySQL 8.x、Redis 7.x
- Docker / Docker Compose（部署阶段）

依赖安装：

```bash
# 后端
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Agent
cd agent && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 前端
cd frontend && npm install
```

## 二、后端分层约定

```
Router (api/v1) → Service → Repository → Model(ORM)
         ↘ Schema(Pydantic) → 请求校验 / 响应格式化
```

| 层 | 职责 | 约束 |
| --- | --- | --- |
| `api/v1/` | 路由注册、参数校验、统一响应 | 不含业务逻辑；不直接操作数据库 |
| `services/` | 业务逻辑、权限判断、告警计算、任务调度 | 一个业务模块一个 service |
| `repositories/` | 数据访问、分页、查询封装 | 只做数据读写，不写业务判断 |
| `models/` | SQLAlchemy ORM 实体 | 与 `sql/ops_monitor_schema.sql` 保持一致 |
| `schemas/` | Pydantic 模型 | 请求校验 + 响应格式化分离 |
| `core/` | 配置、安全（JWT/密码）、数据库、日志 | 全局单例 |
| `middleware/` | 通用中间件（请求日志、审计等） | - |
| `exceptions/` | 统一异常定义与处理器 | - |
| `utils/` | 通用工具函数 | - |

## 三、统一响应格式

所有接口返回统一结构：

```json
{
    "code": 0,
    "message": "ok",
    "data": {}
}
```

`code = 0` 表示成功；业务失败返回对应错误码。

### 错误码

| 错误码 | 含义 |
| --- | --- |
| 400 | 参数错误 |
| 401 | 未登录或 Token 无效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 500 | 服务器内部错误 |

```json
{
    "code": 40001,
    "message": "服务器不存在",
    "data": null
}
```

## 四、安全规范

1. 密码使用 bcrypt 哈希存储，禁止明文。
2. Agent Token 仅存 SHA-256 哈希，不保存明文。
3. 接口统一 JWT 身份校验；按角色判断接口权限。
4. Agent 上报接口独立鉴权（Token），不走用户 JWT。
5. **禁止将用户输入直接拼接进 Shell 命令**。服务操作须经过：服务名白名单校验 → 角色权限校验 → 操作类型校验 → Agent 端二次校验 → 记录审计日志。
6. 操作日志 `request_params` 禁止记录密码与 Token。
7. 高风险操作（服务重启、删除等）需二次确认。

## 五、日志规范

| 日志类型 | 内容 | 存储 |
| --- | --- | --- |
| 应用日志 | API 请求、异常、数据库错误、启动/关闭 | 文件 / stdout |
| Agent 日志 | 启动、注册、心跳、采集、上报、网络异常、任务执行 | 文件 |
| 操作日志 | 登录、服务器增删、服务操作、任务执行、告警确认、权限修改 | `sys_operation_log` |
| 登录日志 | 登录成功/失败 | `sys_login_log` |
| 告警日志 | 告警状态变化 | `alert_event_log` |
| 任务日志 | 任务执行明细 | `ops_task_log` |

## 六、接口约定

- 前缀统一 `/api/v1`
- 资源接口使用 RESTful 风格：`GET /resource`、`GET/PUT/DELETE /resource/{id}`、`POST /resource`
- Agent 接口：`POST /api/v1/agent/register`、`/heartbeat`、`/metrics`、`/task/result`
- 列表接口支持分页参数 `page`、`page_size`，返回 `{ total, items }`

## 七、Git 提交规范

- **原子化提交**：一次提交一个逻辑改动，便于回滚与 review。
- **重要功能独立分支**：功能开发使用 `feature/xxx` 分支，稳定后合入主干。
- 提交信息格式：`<type>(<scope>): <subject>`，例如：
  - `feat(auth): 新增登录接口`
  - `fix(metric): 修复磁盘使用率计算错误`
  - `chore: 更新依赖`
  - `docs: 补充数据库设计文档`

## 八、开发原则

1. 优先保证核心功能稳定，再扩展。
2. 涉及服务器操作必须权限校验。
3. 关键运维操作必须具备可追溯审计日志。
4. 前后端通过明确 RESTful API 交互。
5. 数据库设计优先考虑查询场景与索引。
6. 监控数据与业务数据逻辑隔离。
7. 每个核心模块进行功能与异常场景测试。
8. 文档与代码实现保持同步。
