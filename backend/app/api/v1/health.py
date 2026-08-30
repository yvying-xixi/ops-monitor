"""健康检查接口。"""

from __future__ import annotations

import redis
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.utils.response import success

router = APIRouter(tags=["健康检查"])


@router.get("/health", summary="健康检查", description="检查数据库与 Redis 连通性，任一组件不可用时返回 503。")
def health(db: Session = Depends(get_db)):
    """健康检查接口。

    Args:
        db: 数据库会话。

    Returns:
        正常时统一响应 `{code:0, data:{db, redis}}`；任一组件异常时 HTTP 503。
    """
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        redis_ok = bool(client.ping())
    except Exception:
        redis_ok = False

    data = {"db": db_ok, "redis": redis_ok}
    if db_ok and redis_ok:
        return success(data=data)
    return JSONResponse(
        status_code=503,
        content={"code": 0, "message": "service unavailable", "data": data},
    )
