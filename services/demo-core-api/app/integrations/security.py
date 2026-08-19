"""Pure integration signing and idempotency primitives.

Persistence-backed nonce replay protection intentionally belongs to the next batch.
"""

import hashlib
import hmac
import re
from collections.abc import Iterable
from uuid import UUID


MAX_BODY_BYTES = 16 * 1024
SIGNATURE_PATTERN = re.compile(r"^v1=([0-9a-f]{64})$")


def validate_body_size(body: bytes) -> None:
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("payload exceeds 16 KiB")


def validate_timestamp(timestamp: int, *, now: int, tolerance_seconds: int = 300) -> None:
    if tolerance_seconds < 0:
        raise ValueError("tolerance must not be negative")
    if abs(now - timestamp) > tolerance_seconds:
        raise ValueError("timestamp is outside the allowed clock-skew window")


def _validate_request_parts(timestamp: int, nonce: str, method: str, path: str) -> None:
    if timestamp < 0:
        raise ValueError("timestamp must be a non-negative unix timestamp")
    if str(UUID(nonce)) != nonce:
        raise ValueError("nonce must be a canonical lowercase UUID")
    if not re.fullmatch(r"[A-Z]+", method):
        raise ValueError("method must be uppercase ASCII")
    if not path.startswith("/") or "\n" in path:
        raise ValueError("path must be an absolute HTTP path without newlines")


def build_signature_base(
    *, timestamp: int, nonce: str, method: str, path: str, body: bytes
) -> bytes:
    validate_body_size(body)
    _validate_request_parts(timestamp, nonce, method, path)
    body_digest = hashlib.sha256(body).hexdigest()
    return f"v1\n{timestamp}\n{nonce}\n{method}\n{path}\n{body_digest}".encode()


def sign_body(
    secret: bytes,
    *,
    timestamp: int,
    nonce: str,
    method: str,
    path: str,
    body: bytes,
) -> str:
    if not secret:
        raise ValueError("secret must not be empty")
    base = build_signature_base(
        timestamp=timestamp, nonce=nonce, method=method, path=path, body=body
    )
    return f"v1={hmac.new(secret, base, hashlib.sha256).hexdigest()}"


def verify_body_signature(
    signature: str,
    secrets: Iterable[bytes],
    *,
    timestamp: int,
    nonce: str,
    method: str,
    path: str,
    body: bytes,
) -> bool:
    if SIGNATURE_PATTERN.fullmatch(signature) is None:
        return False
    candidates = tuple(secrets)
    if not candidates or any(not secret for secret in candidates):
        raise ValueError("at least one non-empty secret is required")
    matched = False
    for secret in candidates:
        matched |= hmac.compare_digest(
            signature,
            sign_body(
                secret,
                timestamp=timestamp,
                nonce=nonce,
                method=method,
                path=path,
                body=body,
            ),
        )
    return matched


def _source_material(calendar_id: str, event_id: str) -> bytes:
    return f"gcal:v1\0{calendar_id}\0{event_id}".encode()


def compute_source_event_key(calendar_id: str, event_id: str) -> str:
    return hashlib.sha256(_source_material(calendar_id, event_id)).hexdigest()


def compute_revision_key(
    calendar_id: str, event_id: str, event_updated_at: str
) -> str:
    material = _source_material(calendar_id, event_id) + b"\0" + event_updated_at.encode()
    return hashlib.sha256(material).hexdigest()


def compute_idempotency_key(
    calendar_id: str, event_id: str, event_updated_at: str
) -> str:
    return f"sha256:{compute_revision_key(calendar_id, event_id, event_updated_at)}"
