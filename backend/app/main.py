"""轻量级服务器运维监控平台 - FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, health, users
from app.core.config import settings
from app.core.seed import init_seed_data
from app.exceptions.handlers import register_exception_handlers
from app.middleware import OperationLogMiddleware, RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时按配置幂等初始化种子数据。"""
    if settings.SEED_INIT_DATA:
        init_seed_data()
    yield


app = FastAPI(
    title="轻量级服务器运维监控平台",
    description="面向 Linux 服务器的轻量级运维监控与自动化管理平台",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 中间件按外层→内层顺序：RequestContext(外层) → OperationLog → 路由
app.add_middleware(OperationLogMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
