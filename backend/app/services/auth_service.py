"""认证服务：登录认证、Token 签发与登录日志。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.exceptions import AppException, ErrorCode
from app.repositories import UserRepository
from app.repositories.audit_repository import LoginLogRepository
from app.schemas.auth import TokenResponse


class AuthService:
    """用户认证业务逻辑。

    Attributes:
        db: SQLAlchemy 会话对象。
        user_repo: 用户仓储。
        login_log_repo: 登录日志仓储。
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.login_log_repo = LoginLogRepository(db)

    def login(
        self,
        username: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
    ) -> TokenResponse:
        """用户登录：校验凭证与账号状态，签发 Token 并记录登录日志。

        Args:
            username: 登录用户名。
            password: 明文密码。
            ip: 登录 IP，可选。
            user_agent: 浏览器 User-Agent，可选。
            request_id: 请求 ID，可选。

        Returns:
            包含 Access Token 与过期时间的响应模型。

        Raises:
            AppException: 用户名或密码错误（40101）、账号禁用（40102）。
        """
        user = self.user_repo.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            self.login_log_repo.create_login_log(
                username=username,
                login_status="FAILED",
                login_ip=ip,
                user_agent=user_agent,
                failure_reason="用户名或密码错误",
                request_id=request_id,
            )
            self.db.commit()
            raise AppException(ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误", http_status=401)

        if user.status != 1:
            self.login_log_repo.create_login_log(
                user_id=user.id,
                username=username,
                login_status="FAILED",
                login_ip=ip,
                user_agent=user_agent,
                failure_reason="账号已禁用",
                request_id=request_id,
            )
            self.db.commit()
            raise AppException(ErrorCode.ACCOUNT_DISABLED, "账号已禁用", http_status=401)

        self.user_repo.update_last_login(user, ip)
        token = create_access_token(user.id)
        self.login_log_repo.create_login_log(
            user_id=user.id,
            username=username,
            login_status="SUCCESS",
            login_ip=ip,
            user_agent=user_agent,
            request_id=request_id,
        )
        self.db.commit()
        return TokenResponse(
            access_token=token,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        )
