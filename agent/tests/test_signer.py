"""Ed25519 请求签名器与客户端签名测试。"""

from __future__ import annotations

import base64
import hashlib

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from agent.reporter.client import AgentClient
from agent.signer import load_or_create_signer


def _canonical(method: str, path: str, headers: dict, body: bytes) -> bytes:
    return (
        f"{method}\n{path}\n{headers['X-Timestamp']}\n{headers['X-Request-Id']}\n"
        f"{hashlib.sha256(body).hexdigest()}"
    ).encode("utf-8")


def test_load_or_create_persists_key(tmp_path):
    key_file = tmp_path / "agent_ed25519.key"
    first = load_or_create_signer(str(key_file), server_code="web-01")
    assert key_file.exists()
    second = load_or_create_signer(str(key_file), server_code="web-01")
    assert first.public_key_b64 == second.public_key_b64


def test_sign_headers_verifiable(tmp_path):
    signer = load_or_create_signer(str(tmp_path / "agent.key"), server_code="web-01")
    body = b'{"a":1}'
    headers = signer.sign_headers("POST", "/api/v1/agent/heartbeat", body)

    assert headers["X-Agent-Id"] == "web-01"
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(signer.public_key_b64))
    public_key.verify(
        base64.b64decode(headers["X-Signature"]),
        _canonical("POST", "/api/v1/agent/heartbeat", headers, body),
    )


def test_client_signs_requests(tmp_path):
    signer = load_or_create_signer(str(tmp_path / "agent.key"), server_code="web-01")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content
        return httpx.Response(200, json={"code": 0, "data": {"ok": True}})

    client = AgentClient(
        "http://test.local", "token", signer=signer, transport=httpx.MockTransport(handler)
    )
    client.post("/api/v1/agent/heartbeat", json={"server_id": 1})

    assert client.signing_public_key == signer.public_key_b64
    assert captured["headers"]["x-agent-id"] == "web-01"
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(signer.public_key_b64))
    public_key.verify(
        base64.b64decode(captured["headers"]["x-signature"]),
        _canonical("POST", "/api/v1/agent/heartbeat", {
            "X-Timestamp": captured["headers"]["x-timestamp"],
            "X-Request-Id": captured["headers"]["x-request-id"],
        }, captured["body"]),
    )
