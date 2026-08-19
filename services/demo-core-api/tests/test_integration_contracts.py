import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from app.integrations.contracts import ConfirmedEventV1, WorkEventV1
from app.integrations.security import (
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


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[3] / "contracts" / "integrations" / "v1"
)


def load_json(relative_path: str) -> dict:
    return json.loads((CONTRACT_ROOT / relative_path).read_text(encoding="utf-8"))


def schema_validator(filename: str) -> Draft202012Validator:
    schema = load_json(filename)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def work_event() -> dict:
    return load_json("fixtures/work-event.valid.json")


@pytest.fixture
def confirmed_event() -> dict:
    return load_json("fixtures/confirmed-event.valid.json")


def test_work_event_fixture_matches_schema_and_pydantic(work_event):
    schema_validator("work-event.schema.json").validate(work_event)
    model = WorkEventV1.model_validate(work_event)

    assert model.model_dump(mode="json") == work_event


@pytest.mark.parametrize(
    ("mutation", "expected_field"),
    [
        (lambda body: body.pop("person_ref"), "person_ref"),
        (lambda body: body.update({"attendees": []}), "attendees"),
        (lambda body: body.update({"schema_version": "2.0"}), "schema_version"),
        (lambda body: body.update({"duration_minutes": 14}), "duration_minutes"),
        (lambda body: body.update({"duration_minutes": 91}), "duration_minutes"),
        (
            lambda body: body.update(
                {"event_updated_at": "2026-08-13T09:15:00+08:00"}
            ),
            "event_updated_at",
        ),
        (lambda body: body.update({"description": "Bearer test-value"}), "description"),
        (lambda body: body.update({"description": "<b>Workshop</b>"}), "description"),
    ],
)
def test_work_event_rejections_match_both_contracts(
    work_event, mutation, expected_field
):
    invalid = deepcopy(work_event)
    mutation(invalid)

    with pytest.raises(JsonSchemaValidationError) as schema_error:
        schema_validator("work-event.schema.json").validate(invalid)
    with pytest.raises(PydanticValidationError) as model_error:
        WorkEventV1.model_validate(invalid)

    assert expected_field in str(schema_error.value)
    assert expected_field in str(model_error.value)


@pytest.mark.parametrize("duration", [15, 30, 1425, 1440])
def test_work_event_duration_boundaries_are_accepted(work_event, duration):
    work_event["duration_minutes"] = duration

    schema_validator("work-event.schema.json").validate(work_event)
    assert WorkEventV1.model_validate(work_event).duration_minutes == duration


def test_confirmed_event_fixture_matches_schema_and_pydantic(confirmed_event):
    schema_validator("confirmed-event.schema.json").validate(confirmed_event)
    model = ConfirmedEventV1.model_validate(confirmed_event)

    assert model.model_dump(mode="json") == confirmed_event


@pytest.mark.parametrize(
    "mutation",
    [
        lambda body: body.update({"event_type": "time_entry.suggested"}),
        lambda body: body.update({"calendar_id": "must-not-leak"}),
        lambda body: body["result"].update({"description": "must-not-reach-slack"}),
        lambda body: body["result"].update({"hours": "1.5"}),
        lambda body: body["result"].update({"hours": "24.25"}),
    ],
)
def test_confirmed_event_rejects_unknown_or_non_allowlisted_fields(
    confirmed_event, mutation
):
    invalid = deepcopy(confirmed_event)
    mutation(invalid)

    with pytest.raises(JsonSchemaValidationError):
        schema_validator("confirmed-event.schema.json").validate(invalid)
    with pytest.raises(PydanticValidationError):
        ConfirmedEventV1.model_validate(invalid)


def test_confirmed_event_result_is_the_slack_field_allowlist(confirmed_event):
    expected = {
        "time_entry_id",
        "person_display_name",
        "project_display_name",
        "work_date",
        "hours",
        "status",
    }
    schema = load_json("confirmed-event.schema.json")

    assert set(schema["properties"]["result"]["properties"]) == expected
    assert set(confirmed_event["result"]) == expected


def test_body_limit_is_exactly_16_kib():
    validate_body_size(b"x" * MAX_BODY_BYTES)

    with pytest.raises(ValueError, match="16 KiB"):
        validate_body_size(b"x" * (MAX_BODY_BYTES + 1))


def test_fixed_hmac_and_idempotency_vector():
    vector = load_json("hmac-test-vector.json")
    body = vector["body_utf8"].encode()
    request = {
        "timestamp": vector["timestamp"],
        "nonce": vector["nonce"],
        "method": vector["method"],
        "path": vector["path"],
        "body": body,
    }

    assert hashlib.sha256(body).hexdigest() == vector["body_sha256"]
    assert build_signature_base(**request).decode() == vector["base_string"]
    assert sign_body(vector["test_key_utf8"].encode(), **request) == vector["signature"]

    event = json.loads(vector["body_utf8"])
    source_key = compute_source_event_key(event["calendar_id"], event["event_id"])
    revision_key = compute_revision_key(
        event["calendar_id"], event["event_id"], event["event_updated_at"]
    )
    assert source_key == vector["source_event_key"]
    assert revision_key == vector["revision_key"]
    assert compute_idempotency_key(
        event["calendar_id"], event["event_id"], event["event_updated_at"]
    ) == vector["idempotency_key"]


def test_hmac_rejects_tampering_and_accepts_rotation_key():
    vector = load_json("hmac-test-vector.json")
    request = {
        "timestamp": vector["timestamp"],
        "nonce": vector["nonce"],
        "method": vector["method"],
        "path": vector["path"],
        "body": vector["body_utf8"].encode(),
    }
    active = b"retired-test-key"
    next_key = vector["test_key_utf8"].encode()

    assert verify_body_signature(vector["signature"], [active, next_key], **request)
    assert not verify_body_signature(
        vector["signature"], [active, next_key], **{**request, "body": b"{}"}
    )
    assert not verify_body_signature("v2=invalid", [next_key], **request)


def test_timestamp_window_rejects_past_and_future_requests():
    now = 1786554000
    validate_timestamp(now - 300, now=now)
    validate_timestamp(now + 300, now=now)

    with pytest.raises(ValueError, match="clock-skew"):
        validate_timestamp(now - 301, now=now)
    with pytest.raises(ValueError, match="clock-skew"):
        validate_timestamp(now + 301, now=now)


def test_event_revision_changes_only_the_revision_key(work_event):
    source_before = compute_source_event_key(
        work_event["calendar_id"], work_event["event_id"]
    )
    revision_before = compute_revision_key(
        work_event["calendar_id"],
        work_event["event_id"],
        work_event["event_updated_at"],
    )

    work_event["event_updated_at"] = "2026-08-13T01:16:00Z"

    assert compute_source_event_key(
        work_event["calendar_id"], work_event["event_id"]
    ) == source_before
    assert compute_revision_key(
        work_event["calendar_id"],
        work_event["event_id"],
        work_event["event_updated_at"],
    ) != revision_before
