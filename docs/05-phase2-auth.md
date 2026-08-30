# 阶段二 · 用户权限模块（后端闭环）

> 对应总体规划「二、用户权限」阶段：登录接口、JWT、路由守卫、权限校验、操作日志。
> 本文档固化设计决策与实施范围，作为 M1–M3 开发的执行基准。

## 一、范围与目标

完成后端登录鉴权闭环，为后续服务器/监控/告警等模块提供统一的身份认证与权限控制底座。

| 里程碑 | 内容 | 交付物 |
| --- | --- | --- |
| M1 | 基础能力层 | 安全工具、统一异常、统一响应 |
| M2 | 登录闭环 + 用户管理 | 登录接口、用户 CRUD、种子数据、Health |
| M3 | 鉴权依赖 + 操作审计 | 鉴权依赖、操作日志中间件、接口权限 |
| M4 | 前端用户权限（本轮不做） | 后端 API 与权限模型稳定后单独推进 |

## 二、已确认决策

1. **范围**：本轮仅 M1–M3 后端闭环；前端 M4 后续单独做。
2. **Token 策略**：单 Access Token + JWT（HS256），`expires_in=7200` 秒（`JWT_EXPIRE_MINUTES=120`）。
3. **种子数据**：应用启动时幂等初始化（按角色编码/用户名检查后插入），由 `SEED_INIT_DATA` 配置控制。
4. **健康接口**：`GET /api/v1/health` 检查 DB + Redis，任一组件不可用返回 HTTP 503 并给出故障组件。
5. **事务边界**：仓储仅 `flush`，Service 层统一 `commit/rollback`。
6. **统一响应**：`{code, message, data}`，`code=0` 表示成功；业务错误码见下。

## 三、统一响应与错误码

### 响应格式

```json
{ "code": 0, "message": "ok", "data": {} }
```

### 错误码

| 错误码 | HTTP | 含义 |
| --- | --- | --- |
| 0 | 200 | 成功 |
| 40000 | 400 | 参数错误（含校验失败） |
| 40100 | 401 | 未认证或 Token 无效 |
| 40101 | 401 | 用户名或密码错误 |
| 40102 | 401 | 账号已禁用 |
| 40300 | 403 | 无权限 |
| 40401 | 404 | 用户不存在 |
| 40402 | 404 | 角色不存在 |
| 40901 | 409 | 用户名已存在 |
| 40902 | 409 | 邮箱已存在 |
| 50000 | 500 | 服务器内部错误 |

## 四、目录设计

```
backend/app/
├── core/
│   ├── config.py        # 新增 JWT_ALGORITHM / CORS_ORIGINS / SEED_*
│   ├── security.py      # 密码哈希、JWT 签发/校验
│   └── seed.py          # 启动幂等种子数据
├── exceptions/
│   ├── error_codes.py   # 错误码常量
│   ├── app_exception.py # AppException
│   └── handlers.py      # 统一异常处理器
├── utils/
│   └── response.py      # success / page 辅助
├── schemas/
│   ├── auth.py          # LoginRequest / TokenResponse
│   └── user.py          # UserCreate / UserUpdate / UserOut
├── services/
│   ├── auth_service.py  # 登录、签发、登录日志
│   └── user_service.py  # 用户 CRUD + 角色分配
├── repositories/
│   └── audit_repository.py  # LoginLogRepository
├── middleware/
│   ├── request_context.py   # X-Request-ID + 当前用户
│   └── operation_log.py     # 操作审计落库
├── api/v1/
│   ├── deps.py          # get_current_user / require_roles
│   ├── auth.py          # POST /api/v1/auth/login
│   ├── users.py         # 用户管理接口
│   └── health.py        # GET /api/v1/health
└── main.py              # FastAPI 实例 + lifespan(seed)
```

## 五、核心接口

| 方法与路径 | 说明 | 权限 |
| --- | --- | --- |
| `POST /api/v1/auth/login` | 登录，返回 `{access_token, token_type, expires_in}` | 公开 |
| `GET /api/v1/health` | DB + Redis 连通检查 | 公开 |
| `GET /api/v1/users` | 用户分页列表 | SYSTEM_ADMIN |
| `POST /api/v1/users` | 创建用户 | SYSTEM_ADMIN |
| `GET /api/v1/users/{id}` | 用户详情 | SYSTEM_ADMIN |
| `PUT /api/v1/users/{id}` | 更新用户 | SYSTEM_ADMIN |
| `DELETE /api/v1/users/{id}` | 软删除用户 | SYSTEM_ADMIN |

## 六、关键实现要点

1. **密码存储**：bcrypt 哈希（passlib），禁止明文；`verify_password` 校验。
2. **JWT**：payload 含 `sub`（用户 ID）、`iat`、`exp`；`decode_access_token` 解析失败统一抛 401。
3. **登录流程**：查用户 → 验密码 → 校验状态 → 更新 `last_login` → 签发 Token → 写 `sys_login_log` → commit；失败同样落登录日志。
4. **鉴权依赖**：`get_current_user`（Token→用户，禁用抛 401）、`require_roles(*role_codes)`（无交集抛 403）。
5. **操作审计**：BaseHTTPMiddleware 跳过 `/health`、`/auth/login`、`/docs`、`/openapi.json`；记录耗时/状态/IP/脱敏参数；独立 `SessionLocal` 写入，`try/except` 永不阻断业务请求。
6. **种子数据**：`init_seed_data()` 幂等创建三个角色（SYSTEM_ADMIN/OPS_ENGINEER/NORMAL_USER）、基础权限集、admin 账号（账号/密码由 `SEED_ADMIN_*` 配置）。
7. **Health**：`SELECT 1` + `redis.ping()`；任一下线返回 503 及 `{db, redis}` 布尔状态。

## 七、配置项（.env）

```ini
JWT_SECRET_KEY=                 # 必填，JWT 签名密钥
JWT_EXPIRE_MINUTES=120          # Token 有效期（分钟），= expires_in 7200 秒
CORS_ORIGINS=*                  # 开发期放行
SEED_INIT_DATA=true             # 启动时是否初始化种子数据
SEED_ADMIN_USERNAME=admin       # 初始管理员账号
SEED_ADMIN_PASSWORD=admin123456 # 初始管理员密码（开发默认值，上线前必改）
```

## 八、测试策略

- **单元**（security / response / exceptions）：纯逻辑。
- **集成**（auth / users / health / deps）：`TestClient` + `dependency_overrides[get_db]` 事务会话，结束后 rollback。
- 全量回归：`cd backend && .venv/bin/python -m pytest app/test/ -v`。

## 九、提交计划

1. `feat(auth): 新增安全工具与统一异常响应`（M1）
2. `feat(auth): 登录接口与用户管理 API`（M2）
3. `feat(auth): 鉴权依赖与操作审计中间件`（M3）

## 十、风险与注意

- passlib 1.7.4 + bcrypt≥4.1 存在已知告警，requirements 锁定 `bcrypt==4.0.1`。
- 种子 admin 密码为开发默认值，需在 README 与上线文档标注强改。
- OAuth2PasswordBearer 仅用于从 Header 提取 Token；登录仍为 JSON 体，Swagger 授权需手动粘贴 Token。
