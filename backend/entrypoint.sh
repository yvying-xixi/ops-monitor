#!/usr/bin/env sh
# 后端容器入口：先执行数据库迁移，再启动服务。
# 迁移在启动 worker 之前同步执行一次，避免多 worker 并发迁移。
set -e

echo "[entrypoint] applying database migrations..."
alembic upgrade head

echo "[entrypoint] starting backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
