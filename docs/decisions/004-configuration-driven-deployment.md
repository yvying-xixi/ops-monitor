# ADR-004: 配置驱动的平台部署

## Status

Accepted

## Context

平台需要便捷、可重复、可维护的部署方式。直接依赖 `docker-compose.yml` + 手工 `.env` 容易出错、难以复核，也不利于备份与重建。

## Decision

采用 **配置驱动部署**（参考 Harbor 模式）：

- 唯一配置源：`deploy/config.yml`（由 `config.yml.tmpl` 生成）。
- 渲染产物：`deploy/.env`（由 `prepare.py` 生成，供 Compose 读取）。
- 脚本职责：`install.sh`（首装）、`reconfigure.sh`（改配置后重建）、`check.sh`（体检）。
- 空密钥由脚本生成并回写 `config.yml`；数据目录由 `data.volume_dir` 指定。

## Alternatives

### 直接编辑 docker-compose 与环境变量

- 优点：无额外脚本。
- 缺点：易错、无校验、配置分散、不可重复。

### 引入编排工具（Ansible/Helm）

- 优点：功能强大、可管理多环境。
- 缺点：对当前轻量项目过重。

## Consequences

### Positive

- 部署可重复、可复核，配置集中。
- 改配置一键重建，数据保留。
- 为离线/预构建镜像部署打基础。

### Negative

- 需维护脚本与配置模板。
- 依赖 `python3 + PyYAML`。
