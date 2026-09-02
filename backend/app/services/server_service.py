"""服务器资产管理服务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import AppException, ErrorCode
from app.models import OpsServer, OpsServerService
from app.repositories import AgentTokenRepository, ServerRepository
from app.repositories.server_repository import ServiceRepository
from app.schemas.server import AgentTokenResponse, ServerCreate


class ServerService:
    """服务器资产管理业务逻辑，事务提交统一在此层完成。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.server_repo = ServerRepository(db)
        self.token_repo = AgentTokenRepository(db)
        self.service_repo = ServiceRepository(db)

    def create_server(self, data: ServerCreate, *, created_by: int | None = None) -> OpsServer:
        """创建服务器资产。

        Args:
            data: 创建请求体。
            created_by: 创建人用户 ID。

        Returns:
            创建的服务器对象。

        Raises:
            AppException: 编码或 IP+端口已存在（40903/40904）。
        """
        if self.server_repo.get_by_server_code(data.server_code):
            raise AppException(ErrorCode.SERVER_CODE_EXISTS, "服务器编码已存在", http_status=409)
        if self.server_repo.get_by_ip_port(data.ip_address, data.ssh_port):
            raise AppException(ErrorCode.SERVER_IP_EXISTS, "IP 与端口已被占用", http_status=409)

        server = OpsServer(
            server_code=data.server_code,
            hostname=data.hostname,
            ip_address=data.ip_address,
            ssh_port=data.ssh_port,
            remark=data.remark,
            agent_status="OFFLINE",
            status=1,
            created_by=created_by,
        )
        self.server_repo.create(server)
        self.db.commit()
        return server

    def list_servers(
        self,
        page: int = 1,
        page_size: int = 20,
        agent_status: str | None = None,
    ) -> tuple[int, list[OpsServer]]:
        """分页查询服务器列表。

        Args:
            page: 页码。
            page_size: 每页数量。
            agent_status: Agent 状态过滤，可选。

        Returns:
            元组 (total, items)。
        """
        filters: dict = {}
        if agent_status:
            filters["agent_status"] = agent_status
        return self.server_repo.list(page=page, page_size=page_size, order_by="-id", **filters)

    def get_server(self, server_id: int) -> OpsServer:
        """按 ID 查询服务器。

        Raises:
            AppException: 服务器不存在（40403）。
        """
        server = self.server_repo.get(server_id)
        if server is None:
            raise AppException(ErrorCode.SERVER_NOT_FOUND, "服务器不存在", http_status=404)
        return server

    def generate_agent_token(self, server_id: int, token_name: str | None = None) -> AgentTokenResponse:
        """生成 Agent 注册凭证，明文仅返回一次。

        Args:
            server_id: 服务器 ID。
            token_name: Token 名称。

        Returns:
            包含明文 Token 的响应模型。
        """
        server = self.get_server(server_id)
        token, plaintext = self.token_repo.create_token(server.id, token_name)
        self.db.commit()
        return AgentTokenResponse(
            id=token.id,
            token_name=token.token_name,
            token_prefix=token.token_prefix,
            token=plaintext,
            created_at=token.created_at,
        )

    def list_services(self, server_id: int) -> list[OpsServerService]:
        """查询服务器的服务资产。"""
        self.get_server(server_id)
        return self.service_repo.list_by_server(server_id)

    def update_service_whitelist(
        self, server_id: int, service_id: int, is_whitelisted: int
    ) -> OpsServerService:
        """更新服务是否允许受控操作。"""
        self.get_server(server_id)
        service = self.service_repo.get(service_id)
        if service is None or service.server_id != server_id:
            raise AppException(ErrorCode.SERVER_NOT_FOUND, "服务不存在", http_status=404)
        self.service_repo.set_whitelist(service, is_whitelisted)
        self.db.commit()
        return service
