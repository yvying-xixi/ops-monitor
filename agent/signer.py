"""Ed25519 请求签名器：生成/加载私钥并构造签名请求头（见 ADR-010）。"""

from __future__ import annotations

import base64
import hashlib
import os
import time
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class AgentSigner:
    """持有 Ed25519 私钥，为 Agent 请求生成签名头。"""

    def __init__(self, private_key: Ed25519PrivateKey, *, server_code: str, key_path: str) -> None:
        self._private_key = private_key
        self._server_code = server_code
        self.key_path = key_path

    @property
    def public_key_b64(self) -> str:
        """base64 编码的 Ed25519 公钥（32 字节）。"""
        raw = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    def sign_headers(self, method: str, path: str, body: bytes) -> dict[str, str]:
        """构造签名请求头。"""
        timestamp = str(int(time.time()))
        request_id = uuid.uuid4().hex
        canonical = (
            f"{method.upper()}\n{path}\n{timestamp}\n{request_id}\n{hashlib.sha256(body).hexdigest()}"
        ).encode("utf-8")
        signature = self._private_key.sign(canonical)
        return {
            "X-Agent-Id": self._server_code,
            "X-Timestamp": timestamp,
            "X-Request-Id": request_id,
            "X-Signature": base64.b64encode(signature).decode("ascii"),
        }


def load_or_create_signer(key_file: str, *, server_code: str) -> AgentSigner:
    """加载私钥；不存在则生成并以 0600 权限落盘。

    Args:
        key_file: 私钥文件路径。
        server_code: 服务器编码（用于 `X-Agent-Id`）。

    Returns:
        AgentSigner 实例。
    """
    path = Path(key_file)
    if path.is_file():
        private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise ValueError(f"签名私钥类型不匹配: {key_file}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        private_key = Ed25519PrivateKey.generate()
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path.write_bytes(pem)
        os.chmod(path, 0o600)
    return AgentSigner(private_key, server_code=server_code, key_path=str(path))
