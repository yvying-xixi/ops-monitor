"""上报客户端：httpx 封装与指数退避重试。"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("agent.reporter")


class ReporterError(Exception):
    """上报异常。"""


class AgentClient:
    """Agent 上报 HTTP 客户端。

    Attributes:
        base_url: 服务端地址。
        token: Agent Token（自动注入 Bearer 头）。
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 10.0,
        retry_max_seconds: int = 60,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {token}"},
        )
        self._retry_max_seconds = retry_max_seconds

    def close(self) -> None:
        self._client.close()

    def post(self, path: str, json: dict | None = None) -> dict:
        """POST 请求并指数退避重试。

        Args:
            path: 接口路径。
            json: 请求体。

        Returns:
            响应中的 `data` 字段。

        Raises:
            ReporterError: 服务端返回非 2xx 或重试后仍失败。
        """
        return self._request("POST", path, json=json)

    def get(self, path: str) -> dict:
        """GET 请求并指数退避重试。

        Args:
            path: 接口路径。

        Returns:
            响应中的 `data` 字段。

        Raises:
            ReporterError: 服务端返回非 2xx 或重试后仍失败。
        """
        return self._request("GET", path)

    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        delay = 1.0
        while True:
            try:
                response = self._client.request(method, path, json=json)
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("请求 %s 失败: %s，%ss 后重试", path, exc, delay)
                if delay >= self._retry_max_seconds:
                    raise ReporterError(f"请求 {path} 最终失败") from exc
                time.sleep(delay)
                delay = min(delay * 2, self._retry_max_seconds)
                continue

            if response.status_code >= 400:
                message = payload.get("message", "unknown error")
                raise ReporterError(f"{path} 返回 {response.status_code}: {message}")

            logger.info("%s %s 成功", method, path)
            if "data" in payload:
                return payload["data"]
            return payload

    def __enter__(self) -> "AgentClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
