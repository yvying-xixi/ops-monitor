"""服务器只读发现接口（白名单 CIDR + 端口/banner 探测，不含凭据与远程安装）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.deps import require_roles
from app.core.config import settings
from app.schemas.discovery import DiscoveryHost, DiscoveryScanRequest
from app.services import discovery_service
from app.utils.response import success

router = APIRouter(prefix="/discovery", tags=["服务器发现"])

admin_only = [Depends(require_roles("SYSTEM_ADMIN"))]


@router.get("/config", summary="发现功能配置", dependencies=admin_only)
def get_discovery_config():
    """返回发现功能的开关、白名单与限制（供管理端展示）。"""
    data = {
        "enabled": settings.DISCOVERY_ENABLED,
        "allowed_cidrs": discovery_service.allowed_cidrs(),
        "max_hosts": settings.DISCOVERY_MAX_HOSTS,
        "ssh_port": settings.DISCOVERY_SSH_PORT,
    }
    return success(data=data)


@router.post("/scan", summary="扫描网段（只读）", dependencies=admin_only)
def scan_network(data: DiscoveryScanRequest):
    """在白名单范围内做只读端口/SSH banner 探测，返回可开放接入的主机。"""
    hosts = discovery_service.scan(data.cidr, data.port)
    items = [DiscoveryHost(**host).model_dump() for host in hosts]
    return success(data={"cidr": data.cidr, "count": len(items), "hosts": items})
