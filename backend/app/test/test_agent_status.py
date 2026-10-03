"""Agent 状态判定测试：按心跳时间刷新 ONLINE/WARNING/OFFLINE。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import OpsServer
from app.repositories import ServerRepository
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _make_server(db, server_code, ip, heartbeat_offset: timedelta | None):
    server = ServerService(db).create_server(
        ServerCreate(server_code=server_code, hostname=server_code, ip_address=ip)
    )
    if heartbeat_offset is not None:
        server.last_heartbeat_at = _utcnow() - heartbeat_offset
        db.flush()
    return server


def test_refresh_agent_statuses(db):
    _make_server(db, "online-01", "10.0.0.1", timedelta(seconds=5))
    _make_server(db, "warn-01", "10.0.0.2", timedelta(seconds=60))
    _make_server(db, "off-01", "10.0.0.3", timedelta(seconds=120))
    _make_server(db, "none-01", "10.0.0.4", None)

    repo = ServerRepository(db)
    repo.refresh_agent_statuses()
    db.commit()

    statuses = {
        s.server_code: s.agent_status
        for s in db.scalars(select(OpsServer)).all()
    }
    assert statuses["online-01"] == "ONLINE"
    assert statuses["warn-01"] == "WARNING"
    assert statuses["off-01"] == "OFFLINE"
    assert statuses["none-01"] == "OFFLINE"
