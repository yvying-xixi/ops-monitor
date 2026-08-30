"""登录日志仓储。"""

from __future__ import annotations

from app.models import SysLoginLog
from app.repositories.base import BaseRepository


class LoginLogRepository(BaseRepository[SysLoginLog]):
    """登录日志仓储，负责 `sys_login_log` 表的写入与查询。"""

    model = SysLoginLog

    def create_login_log(
        self,
        *,
        username: str,
        login_status: str,
        user_id: int | None = None,
        login_ip: str | None = None,
        user_agent: str | None = None,
        failure_reason: str | None = None,
        request_id: str | None = None,
    ) -> SysLoginLog:
        """记录一条登录日志。

        Args:
            username: 登录用户名。
            login_status: 登录结果，SUCCESS/FAILED/LOCKED。
            user_id: 用户 ID，登录失败且无对应用户时可为空。
            login_ip: 登录 IP。
            user_agent: 浏览器 User-Agent。
            failure_reason: 失败原因，可选。
            request_id: 请求 ID，可选。

        Returns:
            已创建的登录日志对象。
        """
        return self.create(
            SysLoginLog(
                user_id=user_id,
                username=username,
                login_ip=login_ip,
                user_agent=user_agent,
                login_status=login_status,
                failure_reason=failure_reason,
                request_id=request_id,
            )
        )
