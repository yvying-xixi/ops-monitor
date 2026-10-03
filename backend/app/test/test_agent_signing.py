"""Agent 请求签名与防重放测试（Ed25519，见 ADR-010）。"""

from __future__ import annotations

import base64
import json
import time
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core import signing
from app.core.config import settings
from app.repositories import AgentTokenRepository
from app.schemas.server import ServerCreate
from app.services.server_service import ServerService

HEARTBEAT_PATH = "/api/v1/agent/heartbeat"


@pytest.fixture()
def agent_ctx(db):
    server = ServerService(db).create_server(
        ServerCreate(server_code="sign-01", hostname="sign-01", ip_address="10.8.0.1")
    )
    result = ServerService(db).generate_agent_token(server.id)
    return server, result.token


def _keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return private_key, base64.b64encode(raw).decode("ascii")


def _signed_headers(
    private_key: Ed25519PrivateKey,
    server_code: str,
    method: str,
    path: str,
    body: bytes,
    timestamp: int | None = None,
    request_id: str | None = None,
) -> dict[str, str]:
    ts = str(int(time.time()) if timestamp is None else timestamp)
    rid = request_id or uuid.uuid4().hex
    canonical = signing.canonical_string(method, path, ts, rid, body)
    signature = base64.b64encode(private_key.sign(canonical)).decode("ascii")
    return {
        "X-Agent-Id": server_code,
        "X-Timestamp": ts,
        "X-Request-Id": rid,
        "X-Signature": signature,
    }


def _register(client, token: str, public_key: str) -> None:
    payload = {
        "server_code": "sign-01",
        "token": token,
        "hostname": "sign-01",
        "agent_version": "1.0.0",
        "signing_public_key": public_key,
    }
    assert client.post("/api/v1/agent/register", json=payload).status_code == 200


def _heartbeat_body(server_id: int) -> bytes:
    return json.dumps(
        {"server_id": server_id, "agent_version": "1.0.0"}, separators=(",", ":")
    ).encode("utf-8")


def _post_heartbeat(client, token, headers, body):
    return client.request(
        "POST",
        HEARTBEAT_PATH,
        content=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", **headers},
    )


def test_register_stores_public_key(client, db, agent_ctx):
    _, token = agent_ctx
    _, public_key = _keypair()
    _register(client, token, public_key)
    db.expire_all()
    record = AgentTokenRepository(db).authenticate(token)
    assert record is not None
    assert record.signing_public_key == public_key
    assert record.signing_algorithm == "ed25519"


def test_signed_request_accepted(client, db, agent_ctx):
    server, token = agent_ctx
    private_key, public_key = _keypair()
    _register(client, token, public_key)

    body = _heartbeat_body(server.id)
    headers = _signed_headers(private_key, server.server_code, "POST", HEARTBEAT_PATH, body)
    assert _post_heartbeat(client, token, headers, body).status_code == 200


def test_invalid_signature_rejected(client, db, agent_ctx):
    server, token = agent_ctx
    private_key, public_key = _keypair()
    _register(client, token, public_key)

    body = _heartbeat_body(server.id)
    headers = _signed_headers(private_key, server.server_code, "POST", HEARTBEAT_PATH, body)
    headers["X-Signature"] = base64.b64encode(b"\x00" * 64).decode("ascii")
    assert _post_heartbeat(client, token, headers, body).status_code == 401


def test_stale_timestamp_rejected(client, db, agent_ctx):
    server, token = agent_ctx
    private_key, public_key = _keypair()
    _register(client, token, public_key)

    body = _heartbeat_body(server.id)
    headers = _signed_headers(
        private_key, server.server_code, "POST", HEARTBEAT_PATH, body,
        timestamp=int(time.time()) - settings.AGENT_SIGNATURE_MAX_SKEW - 60,
    )
    assert _post_heartbeat(client, token, headers, body).status_code == 401


def test_replayed_request_rejected(client, db, agent_ctx):
    server, token = agent_ctx
    private_key, public_key = _keypair()
    _register(client, token, public_key)

    body = _heartbeat_body(server.id)
    headers = _signed_headers(private_key, server.server_code, "POST", HEARTBEAT_PATH, body)
    assert _post_heartbeat(client, token, headers, body).status_code == 200
    # 重放同一 request_id / 签名
    assert _post_heartbeat(client, token, headers, body).status_code == 401


def test_require_signature_rejects_unsigned(client, db, agent_ctx):
    server, token = agent_ctx
    original = settings.AGENT_REQUIRE_SIGNATURE
    settings.AGENT_REQUIRE_SIGNATURE = True
    try:
        resp = client.post(
            HEARTBEAT_PATH,
            json={"server_id": server.id, "agent_version": "1.0.0"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
    finally:
        settings.AGENT_REQUIRE_SIGNATURE = original


def test_unsigned_allowed_when_not_required(client, db, agent_ctx):
    server, token = agent_ctx
    resp = client.post(
        HEARTBEAT_PATH,
        json={"server_id": server.id, "agent_version": "1.0.0"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_register_rotates_public_key(client, db, agent_ctx):
    _, token = agent_ctx
    _, first_key = _keypair()
    _, second_key = _keypair()
    _register(client, token, first_key)
    _register(client, token, second_key)
    db.expire_all()
    record = AgentTokenRepository(db).authenticate(token)
    assert record is not None
    assert record.signing_public_key == second_key


def _rotate(client, token: str, public_key: str):
    return client.post(
        "/api/v1/agent/signing-key",
        json={"signing_public_key": public_key},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_rotate_signing_key_endpoint(client, db, agent_ctx):
    server, token = agent_ctx
    private_a, public_a = _keypair()
    _register(client, token, public_a)

    private_b, public_b = _keypair()
    assert _rotate(client, token, public_b).status_code == 200
    db.expire_all()
    record = AgentTokenRepository(db).authenticate(token)
    assert record is not None and record.signing_public_key == public_b

    # 新密钥签名通过
    body = _heartbeat_body(server.id)
    new_headers = _signed_headers(private_b, server.server_code, "POST", HEARTBEAT_PATH, body)
    assert _post_heartbeat(client, token, new_headers, body).status_code == 200
    # 旧密钥签名失败
    old_headers = _signed_headers(private_a, server.server_code, "POST", HEARTBEAT_PATH, body)
    assert _post_heartbeat(client, token, old_headers, body).status_code == 401


def test_rotate_invalid_key_rejected(client, db, agent_ctx):
    _, token = agent_ctx
    assert _rotate(client, token, "not-base64!!").status_code == 400
