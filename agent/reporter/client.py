"""上报客户端：httpx 封装与指数退避重试。"""

from __future__ import annotations

import json as _json
import logging
import random
import time
from typing import Any

import httpx

from agent.signer import AgentSigner

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
        retry_max_count: int = 2,
        retry_jitter: bool = True,
        signer: AgentSigner | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {token}"},
        )
        self._retry_max_seconds = retry_max_seconds
        self._retry_max_count = retry_max_count
        self._retry_jitter = retry_jitter
        self._signer = signer

    @property
    def signing_public_key(self) -> str | None:
        """base64 Ed25519 公钥；未配置签名时为 None。"""
        return self._signer.public_key_b64 if self._signer is not None else None

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
        # 启用签名时自行序列化 body，确保签名内容与服务端收到的原始字节一致
        body: bytes | None = None
        signed_headers: dict[str, str] | None = None
        if self._signer is not None:
            body = (
                b""
                if json is None
                else _json.dumps(json, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            )
            signed_headers = self._signer.sign_headers(method, path, body)
            if json is not None:
                signed_headers["Content-Type"] = "application/json"

        delay = 1.0
        attempt = 0
        while True:
            try:
                if self._signer is not None:
                    response = self._client.request(
                        method,
                        path,
                        content=body if json is not None else None,
                        headers=signed_headers,
                    )
                else:
                    response = self._client.request(method, path, json=json)
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                attempt += 1
                if attempt > self._retry_max_count:
                    raise ReporterError(f"请求 {path} 超过最大重试次数") from exc
                if delay >= self._retry_max_seconds:
                    raise ReporterError(f"请求 {path} 最终失败") from exc
                sleep_for = delay
                if self._retry_jitter:
                    sleep_for = delay * (0.5 + random.random())
                sleep_for = min(sleep_for, self._retry_max_seconds)
                logger.warning("请求 %s 失败: %s，%.2fs 后重试（第 %s 次）", path, exc, sleep_for, attempt)
                time.sleep(sleep_for)
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
