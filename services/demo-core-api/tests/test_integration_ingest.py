import json
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.integrations.config import IngestIntegrationConfig
from app.integrations.ingest import INGEST_PATH
from app.integrations.security import compute_idempotency_key, sign_body
from app.main import create_app
from app.models import (
    AuditEvent,
    IntegrationSuggestion,
    IntegrationSuggestionRevision,
    IntegrationSource,
    TimeEntry,
    TimeEntrySourceLink,
)


TEST_SECRET = b"fictional-ingest-test-key"


@pytest.fixture
def integration_client():
    config = IngestIntegrationConfig(
        active_secret=TEST_SECRET,
        enabled=True,
        mode="simulated",
    )
    app = create_app("sqlite://", seed=True, integration_config=config)
    with TestClient(app) as client:
        yield client, app


def work_event() -> dict:
    now = datetime.now(UTC).replace(microsecond=0)
    return {
        "schema_version": "1.0",
        "source": "google_calendar",
        "source_account_ref": "google-test-account-01",
        "calendar_id": "portfolio-work-calendar",
        "event_id": "fictional-event-001",
        "event_updated_at": now.isoformat().replace("+00:00", "Z"),
        "person_ref": "jamie-rivera",
        "project_code": "APOLLO",
        "work_date": date.today().isoformat(),
        "duration_minutes": 90,
        "description": "Prepared fictional customer workshop",
    }


def signed_request(
    event: dict,
    *,
    nonce: str | None = None,
    timestamp: int | None = None,
    secret: bytes = TEST_SECRET,
    idempotency_key: str | None = None,
):
    body = json.dumps(event, separators=(",", ":")).encode()
    resolved_nonce = nonce or str(uuid4())
    resolved_timestamp = timestamp or int(datetime.now(UTC).timestamp())
    signature = sign_body(
        secret,
        timestamp=resolved_timestamp,
        nonce=resolved_nonce,
        method="POST",
        path=INGEST_PATH,
        body=body,
    )
    headers = {
        "Content-Type": "application/json",
        "X-Request-ID": "req_ingest_test",
        "X-Acme-Integration-Id": "n8n-calendar-v1",
        "X-Acme-Timestamp": str(resolved_timestamp),
        "X-Acme-Nonce": resolved_nonce,
        "X-Acme-Idempotency-Key": idempotency_key
        or compute_idempotency_key(
            event["calendar_id"], event["event_id"], event["event_updated_at"]
        ),
        "X-Acme-Signature": signature,
    }
    return body, headers


def test_signed_ingest_creates_only_a_suggestion(integration_client):
    client, app = integration_client
    event = work_event()
    body, headers = signed_request(event)

    with app.state.session_factory() as session:
        entries_before = session.scalar(select(func.count(TimeEntry.id)))
    response = client.post(INGEST_PATH, content=body, headers=headers)

    assert response.status_code == 201
    assert response.json()["status"] == "suggested"
    assert response.json()["duplicate"] is False
    assert "confirmation_token" not in response.text
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(TimeEntry.id))) == entries_before
        suggestion = session.scalar(select(IntegrationSuggestion))
        assert suggestion.actor_id == 3
        assert suggestion.project_id == 1
        assert suggestion.description == event["description"]
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "integration_suggestion_created"
            )
        )
        assert event["description"] not in audit.details

        source = session.scalar(select(IntegrationSource))
        assert source.source_account_ref_hash != event["source_account_ref"]
        assert source.calendar_id_hash != event["calendar_id"]


def test_same_revision_is_idempotent_with_a_fresh_nonce(integration_client):
    client, app = integration_client
    event = work_event()
    first_body, first_headers = signed_request(event)
    first = client.post(INGEST_PATH, content=first_body, headers=first_headers)
    second_body, second_headers = signed_request(event)
    second = client.post(INGEST_PATH, content=second_body, headers=second_headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["suggestion_id"] == first.json()["suggestion_id"]
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(IntegrationSuggestion.id))) == 1
        assert session.scalar(
            select(func.count(IntegrationSuggestionRevision.id))
        ) == 1


def test_new_revision_updates_the_existing_suggestion(integration_client):
    client, app = integration_client
    event = work_event()
    first_body, first_headers = signed_request(event)
    first = client.post(INGEST_PATH, content=first_body, headers=first_headers)
    event["event_updated_at"] = (
        datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=1)
    ).isoformat().replace("+00:00", "Z")
    event["description"] = "Updated fictional customer workshop"
    second_body, second_headers = signed_request(event)
    second = client.post(INGEST_PATH, content=second_body, headers=second_headers)

    assert second.status_code == 201
    assert second.json()["suggestion_id"] == first.json()["suggestion_id"]
    assert second.json()["preview"]["description"] == event["description"]
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(IntegrationSuggestion.id))) == 1
        assert session.scalar(
            select(func.count(IntegrationSuggestionRevision.id))
        ) == 2


def test_reused_nonce_is_rejected(integration_client):
    client, _ = integration_client
    event = work_event()
    nonce = str(uuid4())
    body, headers = signed_request(event, nonce=nonce)

    assert client.post(INGEST_PATH, content=body, headers=headers).status_code == 201
    replay = client.post(INGEST_PATH, content=body, headers=headers)

    assert replay.status_code == 401
    assert replay.json()["code"] == "replayed_nonce"


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        (lambda event: event.update({"person_ref": "unknown-person"}), "mapping_not_found"),
        (lambda event: event.update({"project_code": "UNKNOWN"}), "mapping_not_found"),
    ],
)
def test_unknown_mappings_are_rejected(integration_client, change, expected_code):
    client, _ = integration_client
    event = work_event()
    change(event)
    body, headers = signed_request(event)

    response = client.post(INGEST_PATH, content=body, headers=headers)

    assert response.status_code == 422
    assert response.json()["code"] == expected_code

    replay = client.post(INGEST_PATH, content=body, headers=headers)
    assert replay.status_code == 401
    assert replay.json()["code"] == "replayed_nonce"


def test_signature_timestamp_and_idempotency_are_enforced(integration_client):
    client, _ = integration_client
    event = work_event()

    body, headers = signed_request(event, secret=b"wrong-fictional-key")
    invalid_secret = client.post(INGEST_PATH, content=body, headers=headers)
    assert invalid_secret.json()["code"] == "invalid_signature"

    body, headers = signed_request(
        event, timestamp=int(datetime.now(UTC).timestamp()) - 301
    )
    expired = client.post(INGEST_PATH, content=body, headers=headers)
    assert expired.json()["code"] == "invalid_signature"

    body, headers = signed_request(event, idempotency_key="sha256:" + "0" * 64)
    mismatch = client.post(INGEST_PATH, content=body, headers=headers)
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "idempotency_key_mismatch"

    body, headers = signed_request(event)
    tampered = body.replace(b"90", b"75", 1)
    tampered_response = client.post(INGEST_PATH, content=tampered, headers=headers)
    assert tampered_response.json()["code"] == "invalid_signature"


def test_payload_limit_is_enforced_before_authentication(integration_client):
    client, _ = integration_client

    response = client.post(
        INGEST_PATH,
        content=b"x" * (16 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_confirmed_source_rejects_a_later_revision(integration_client):
    client, app = integration_client
    event = work_event()
    body, headers = signed_request(event)
    first = client.post(INGEST_PATH, content=body, headers=headers)
    with app.state.session_factory() as session:
        suggestion = session.get(IntegrationSuggestion, first.json()["suggestion_id"])
        session.add(
            TimeEntrySourceLink(
                integration_id=suggestion.integration_id,
                source_event_key=suggestion.source_event_key,
                suggestion_id=suggestion.id,
                time_entry_id=1,
            )
        )
        session.commit()
    later = deepcopy(event)
    later["event_updated_at"] = (
        datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=2)
    ).isoformat().replace("+00:00", "Z")
    body, headers = signed_request(later)

    response = client.post(INGEST_PATH, content=body, headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "source_already_confirmed"


def test_integration_is_disabled_without_runtime_secret(client):
    event = work_event()
    body, headers = signed_request(event)

    response = client.post(INGEST_PATH, content=body, headers=headers)

    assert response.status_code == 403
    assert response.json()["code"] == "integration_disabled"
