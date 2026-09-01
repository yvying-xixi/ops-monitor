# 阶段四 · 监控中心

> 对应总体规划「四、监控中心」：服务器详情指标查询、Dashboard 可视化。
> 文档固化设计决策与接口约定，供开发与协作参考。

## 一、范围

- 后端：指标查询（latest/history/summary）、Dashboard 汇总、当前用户/角色信息、角色列表
- 前端：Vue 管理端骨架（登录/布局/路由守卫）+ Dashboard + 服务器列表/详情 + ECharts 图表
- 指标范围沿用阶段三决策：CPU/Memory/Disk/Network/Load/TCP/Uptime；Docker/进程后置

## 二、接口设计

| 方法与路径 | 说明 | 权限 |
| --- | --- | --- |
| `GET /api/v1/servers/{id}/metrics/latest` | 最近一条指标 | 登录 |
| `GET /api/v1/servers/{id}/metrics/history` | 原始历史（分页，start/end/page/page_size） | 登录 |
| `GET /api/v1/servers/{id}/metrics/summary?range=1h\|6h\|24h\|7d` | 分桶聚合，网络输出差分速率 | 登录 |
| `GET /api/v1/servers/{id}/assets` | 磁盘/网卡资产 | 登录 |
| `GET /api/v1/dashboard/overview` | 状态统计 + 平均使用率 + 服务器列表 | 登录 |
| `GET /api/v1/auth/me` | 当前用户信息（含角色） | 登录 |
| `GET /api/v1/roles` | 角色列表（用户管理下拉） | SYSTEM_ADMIN |

## 三、聚合与差分

### 时间桶

| range | 时长 | 桶宽 | 点数上限 |
| --- | --- | --- | --- |
| 1h | 3600s | 60s | 60 |
| 6h | 21600s | 60s | 360 |
| 24h | 86400s | 300s | 288 |
| 7d | 604800s | 3600s | 168 |

### 聚合方式
- 数值指标（CPU/内存/磁盘/Load/TCP）：SQL `FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(collected_at)/N)*N)` 分桶 + `AVG/MAX/MIN`
- 网络指标为**累计字节数**，桶内取 MAX 采样，服务层对相邻桶做差分得到速率（MB/s）

### summary 响应结构

```json
{
  "range": "1h", "bucket_seconds": 60,
  "start": "...", "end": "...",
  "points": [
    {
      "time": "...",
      "cpu_usage": {"avg": 42.5, "max": 88.0, "min": 10.0},
      "memory_usage": {...}, "disk_usage": {...},
      "load_1m": {...}, "load_5m": {...}, "load_15m": {...},
      "tcp_connections": {...},
      "network_in_rate": 0.12, "network_out_rate": 0.05
    }
  ]
}
```

## 四、Dashboard overview

```json
{
  "server_stats": {"ONLINE": 1, "WARNING": 0, "OFFLINE": 0, "UNKNOWN": 0, "total": 1},
  "avg_usage": {"cpu": 42.5, "memory": 60.0, "disk": 70.0},
  "servers": [{"server": {...}, "latest": {"cpu_usage": ..., "memory_usage": ..., "disk_usage": ..., "load_1m": ..., "tcp_connections": ...}}]
}
```

- 平均使用率基于**每台服务器最新指标**计算，无指标的服务器不计入

## 五、前端结构

```
frontend/src/
├── utils/request.js      # axios 拦截器（Token 注入、401 跳登录、统一解包）
├── utils/format.js       # 字节/时长/时间格式化
├── api/                  # auth/server/monitor/user/role 封装
├── store/user.js         # Pinia：Token 持久化、登录/登出、角色判断
├── router/index.js       # 路由 + 守卫（未登录/角色限制）
├── layout/index.vue      # 侧边菜单 + 顶栏，按角色渲染
├── components/MetricChart.vue  # ECharts 通用折线（avg/max/min、速率）
└── views/
    ├── login/index.vue
    ├── dashboard/index.vue     # 统计卡片 + 服务器列表（10s 刷新）
    ├── server/index.vue        # 列表/分页/新增/生成凭证
    ├── server/detail.vue       # 实时卡片 + 历史图表 + 资产
    └── system/user.vue         # 用户管理（admin）
```

## 六、其他

- **保留期清理**：APScheduler 每日执行，删除超过 `METRIC_RETENTION_DAYS`（默认 7 天）的历史指标，`METRIC_CLEANUP_ENABLED` 控制
- **前端代理**：`vite.config.js` 将 `/api` 代理到 `http://127.0.0.1:8000`
- **测试**：`test_monitor_api.py`（latest/history/summary 聚合与网络速率差分）、`test_dashboard_api.py`
