from fastapi.testclient import TestClient
import pytest

from app.integrations.config import IngestIntegrationConfig
from app.main import create_app


EMPLOYEE = {"X-Actor-ID": "3"}


def test_public_mock_is_actor_scoped_and_idempotent(client):
    first = client.post("/integration-suggestions/mock", headers=EMPLOYEE)
    repeated = client.post("/integration-suggestions/mock", headers=EMPLOYEE)
    manager = client.post(
        "/integration-suggestions/mock", headers={"X-Actor-ID": "2"}
    )

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert first.json()["mode"] == "simulated"
    assert repeated.status_code == 200
    assert repeated.json() == {
        "suggestion_id": first.json()["suggestion_id"],
        "created": False,
        "mode": "simulated",
    }
    assert manager.status_code == 403
    suggestions = client.get("/integration-suggestions", headers=EMPLOYEE).json()
    assert len(suggestions) == 1
    assert suggestions[0]["source_label"] == "Google Calendar · simulated"


def test_confirmed_mock_event_cannot_create_a_second_time_entry(client):
    suggestion_id = client.post(
        "/integration-suggestions/mock", headers=EMPLOYEE
    ).json()["suggestion_id"]
    suggestion = client.get("/integration-suggestions", headers=EMPLOYEE).json()[0]
    prepared = client.post(
        f"/integration-suggestions/{suggestion_id}/prepare",
        headers=EMPLOYEE,
        json={
            "project_id": suggestion["project_id"],
            "work_date": suggestion["work_date"],
            "hours": suggestion["hours"],
            "description": suggestion["description"],
        },
    )
    confirmed = client.post(
        f"/actions/{prepared.json()['confirmation_token']}/confirm",
        headers=EMPLOYEE,
        json={"confirm": True},
    )
    repeated = client.post("/integration-suggestions/mock", headers=EMPLOYEE)

    assert confirmed.status_code == 200
    assert repeated.status_code == 409
    assert repeated.json()["detail"] == (
        "This simulated Calendar event is already confirmed"
    )
    previews = client.get(
        "/integration-notifications/preview", headers=EMPLOYEE
    ).json()
    assert len(previews) == 1
    assert previews[0]["delivery_mode"] == "simulated"


def test_public_mock_can_be_disabled():
    app = create_app(
        "sqlite://",
        seed=True,
        integration_config=IngestIntegrationConfig(public_mock_enabled=False),
    )
    with TestClient(app) as test_client:
        response = test_client.post(
            "/integration-suggestions/mock", headers=EMPLOYEE
        )
    assert response.status_code == 404


def test_public_mode_refuses_real_integration_secrets(monkeypatch):
    monkeypatch.setenv("COPILOT_PUBLIC_MOCK_ENABLED", "true")
    monkeypatch.setenv("COPILOT_INGEST_HMAC_SECRET", "must-not-enter-public-mode")

    with pytest.raises(
        RuntimeError,
        match="Public simulated integration refuses real integration secrets",
    ):
        IngestIntegrationConfig.from_env()
