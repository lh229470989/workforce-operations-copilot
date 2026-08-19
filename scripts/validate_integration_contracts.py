#!/usr/bin/env python3
"""Validate public integration fixtures and the frozen cross-system test vector."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.integrations.contracts import ConfirmedEventV1, WorkEventV1
from app.integrations.security import (
    build_signature_base,
    compute_idempotency_key,
    compute_revision_key,
    compute_source_event_key,
    sign_body,
)
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "integrations" / "v1"


def load_json(relative_path: str) -> dict:
    return json.loads((CONTRACT_ROOT / relative_path).read_text(encoding="utf-8"))


def validate_fixture(schema_name: str, fixture_name: str, model_type: type) -> None:
    schema = load_json(schema_name)
    fixture = load_json(f"fixtures/{fixture_name}")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(fixture)
    model_type.model_validate(fixture)


def validate_vector() -> None:
    vector = load_json("hmac-test-vector.json")
    body = vector["body_utf8"].encode()
    request = {
        "timestamp": vector["timestamp"],
        "nonce": vector["nonce"],
        "method": vector["method"],
        "path": vector["path"],
        "body": body,
    }
    event = json.loads(vector["body_utf8"])

    assert hashlib.sha256(body).hexdigest() == vector["body_sha256"]
    assert build_signature_base(**request).decode() == vector["base_string"]
    assert sign_body(vector["test_key_utf8"].encode(), **request) == vector["signature"]
    assert compute_source_event_key(
        event["calendar_id"], event["event_id"]
    ) == vector["source_event_key"]
    assert compute_revision_key(
        event["calendar_id"], event["event_id"], event["event_updated_at"]
    ) == vector["revision_key"]
    assert compute_idempotency_key(
        event["calendar_id"], event["event_id"], event["event_updated_at"]
    ) == vector["idempotency_key"]


def main() -> None:
    validate_fixture(
        "work-event.schema.json", "work-event.valid.json", WorkEventV1
    )
    validate_fixture(
        "confirmed-event.schema.json", "confirmed-event.valid.json", ConfirmedEventV1
    )
    validate_vector()
    print("Integration contracts v1 validated.")


if __name__ == "__main__":
    main()
