# 权限（RBAC）

> 本文描述基于角色的访问控制模型与接口权限。

## 模型

```text
sys_user ──< sys_user_role >── sys_role ──< sys_role_permission >── sys_permission
```

- 用户与角色、角色与权限均为多对多。
- 权限类型：`MENU` / `API` / `BUTTON`。
- 权限自关联（`parent_id`）支持菜单树。

## 默认角色

| 角色编码 | 名称 | 权限概述 |
| --- | --- | --- |
| `SYSTEM_ADMIN` | 系统管理员 | 用户/角色/服务器/监控/告警/任务/日志全部管理 |
| `OPS_ENGINEER` | 运维人员 | 服务器监控、服务管理、运维任务、告警处理 |
| `NORMAL_USER` | 普通用户 | 查看授权服务器及监控数据 |

## 接口鉴权

- 依赖：`get_current_user`（解析 Token → 用户，禁用抛 401）、`require_roles(*role_codes)`（角色交集校验，失败抛 403）。
- 典型限制：
  - 用户管理 `/users`：`SYSTEM_ADMIN`
  - 服务器管理写操作：`SYSTEM_ADMIN`
  - 告警确认/恢复、任务操作：`SYSTEM_ADMIN`/`OPS_ENGINEER`
  - 监控查询：登录用户

## 前端权限

- `store/user.js` 提供 `hasRole`/`isAdmin`。
- 路由 `meta.roles` 限制页面；菜单按角色渲染。

## 错误码

| 错误码 | HTTP | 含义 |
| --- | --- | --- |
| 40300 | 403 | 无权限 |
| 40301 | 403 | 服务不允许受控操作 |

## TODO

> **TODO**: 补充权限码（`sys_permission`）与接口的完整映射清单。
