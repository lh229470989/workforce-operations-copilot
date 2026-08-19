"""Versioned contracts and deterministic integration security helpers."""

from .contracts import ConfirmedEventV1, WorkEventV1
from .security import (
    MAX_BODY_BYTES,
    build_signature_base,
    compute_idempotency_key,
    compute_revision_key,
    compute_source_event_key,
    sign_body,
    validate_body_size,
    validate_timestamp,
    verify_body_signature,
)

__all__ = [
    "ConfirmedEventV1",
    "MAX_BODY_BYTES",
    "WorkEventV1",
    "build_signature_base",
    "compute_idempotency_key",
    "compute_revision_key",
    "compute_source_event_key",
    "sign_body",
    "validate_body_size",
    "validate_timestamp",
    "verify_body_signature",
]
