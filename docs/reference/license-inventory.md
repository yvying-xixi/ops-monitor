# 依赖许可证清单（License Inventory）

> 本文档为**只读分析**结果，用于后续确定项目许可证。本轮不创建 `LICENSE` 文件。
> 数据来源：已安装依赖的包元数据（`importlib.metadata` / `node_modules/*/package.json`）。

## 直接依赖

### Backend（Python）

| Dependency | Version | Type | License |
| --- | --- | --- | --- |
| fastapi | 0.115.0 | Direct | MIT |
| uvicorn | 0.30.6 | Direct | BSD |
| sqlalchemy | 2.0.32 | Direct | MIT |
| pydantic | 2.8.2 | Direct | MIT |
| pydantic-settings | 2.4.0 | Direct | MIT |
| pymysql | 1.1.1 | Direct | MIT |
| redis | 5.0.8 | Direct | MIT |
| pyjwt | 2.9.0 | Direct | MIT |
| passlib | 1.7.4 | Direct | BSD |
| bcrypt | 4.0.1 | Direct | Apache-2.0 |
| apscheduler | 3.10.4 | Direct | MIT |
| croniter | 6.2.4 | Direct | MIT |
| psutil | 5.9.8 | Direct | BSD-3-Clause |
| python-multipart | 0.0.9 | Direct | Apache-2.0 |
| pytest | 8.3.2 | Direct (dev) | MIT |
| httpx | 0.27.0 | Direct (test) | BSD |

### Agent（Python）

| Dependency | Version | Type | License |
| --- | --- | --- | --- |
| psutil | 5.9.8 | Direct | BSD-3-Clause |
| httpx | 0.27.0 | Direct | BSD |
| pydantic | 2.8.2 | Direct | MIT |
| pydantic-settings | 2.4.0 | Direct | MIT |
| pyyaml | 6.0.2 | Direct | MIT |
| pytest | 8.3.2 | Direct (dev) | MIT |

### Frontend（Node）

| Dependency | Version | Type | License |
| --- | --- | --- | --- |
| vue | 3.5.41 | Direct | MIT |
| vue-router | 4.6.4 | Direct | MIT |
| pinia | 2.3.1 | Direct | MIT |
| element-plus | 2.14.5 | Direct | MIT |
| @element-plus/icons-vue | 2.3.2 | Direct | MIT |
| axios | 1.19.0 | Direct | MIT |
| echarts | 5.6.0 | Direct | Apache-2.0 |
| vite | 8.2.2 | Direct (dev) | MIT |
| @vitejs/plugin-vue | 6.0.8 | Direct (dev) | MIT |

## 观察

- 直接依赖以 MIT / BSD / Apache-2.0 为主，均属宽松许可。
- 含 Apache-2.0 依赖（bcrypt、python-multipart、echarts），与 MIT 兼容。

## TODO

> **TODO**: 补充**传递依赖**的许可证清单。
> **TODO**: 确认仓库中是否包含第三方源码及其许可证。
> **TODO**: 依据依赖与来源分析结果，确定项目许可证类型并新增 `LICENSE`。
