"""Agent 请求签名（Ed25519）与 canonical 串构造。

签名串：`METHOD\\nPATH\\nTIMESTAMP\\nREQUEST_ID\\nSHA256_HEX(body)`。
详见 ADR-010。
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def body_sha256(body: bytes) -> str:
    """请求体的 SHA-256 十六进制摘要。"""
    return hashlib.sha256(body).hexdigest()


def canonical_string(method: str, path: str, timestamp: str, request_id: str, body: bytes) -> bytes:
    """构造用于签名的规范化字符串。"""
    raw = f"{method.upper()}\n{path}\n{timestamp}\n{request_id}\n{body_sha256(body)}"
    return raw.encode("utf-8")


def verify_signature(public_key_b64: str, signature_b64: str, canonical: bytes) -> bool:
    """使用 base64 Ed25519 公钥验证 base64 签名。

    Args:
        public_key_b64: base64 编码的公钥（32 字节）。
        signature_b64: base64 编码的签名（64 字节）。
        canonical: 待验证的规范化字符串。

    Returns:
        验证通过返回 True，否则 False。
    """
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, canonical)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
