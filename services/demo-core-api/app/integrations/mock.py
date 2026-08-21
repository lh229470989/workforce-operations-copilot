"""Credential-free, deterministic public demo adapter for a fictional event."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from sqlalchemy import select

from ..auth import ActorDep, SessionDep
from ..models import (
    AuditEvent,
    IntegrationPersonMapping,
    IntegrationProjectMapping,
    IntegrationSource,
    IntegrationSuggestion,
    IntegrationSuggestionRevision,
    Project,
    ProjectMember,
    TimeEntrySourceLink,
)
from .config import IngestIntegrationConfig
from .security import compute_revision_key, compute_source_event_key


MOCK_EVENT_ID = "fictional-public-calendar-event-001"
MOCK_UPDATED_AT = "2026-08-21T01:15:00Z"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def register_mock_routes(app: FastAPI, config: IngestIntegrationConfig) -> None:
    @app.post("/integration-suggestions/mock", tags=["integrations"])
    def create_mock_suggestion(session: SessionDep, actor: ActorDep) -> dict:
        if not config.public_mock_enabled or config.mode != "simulated":
            raise HTTPException(404, "Simulated integration is unavailable")

        source = session.scalar(
            select(IntegrationSource).where(
                IntegrationSource.integration_id == config.integration_id,
                IntegrationSource.enabled.is_(True),
                IntegrationSource.mode == "simulated",
            )
        )
        person = session.scalar(
            select(IntegrationPersonMapping).where(
                IntegrationPersonMapping.integration_id == config.integration_id,
                IntegrationPersonMapping.actor_id == actor.id,
            )
        )
        if source is None or person is None:
            raise HTTPException(403, "This demo persona has no simulated Calendar mapping")
        project_mapping = session.scalar(
            select(IntegrationProjectMapping).where(
                IntegrationProjectMapping.integration_id == config.integration_id,
                IntegrationProjectMapping.project_code == "APOLLO",
            )
        )
        project = session.get(Project, project_mapping.project_id) if project_mapping else None
        membership = session.scalar(
            select(ProjectMember).where(
                ProjectMember.employee_id == actor.id,
                ProjectMember.project_id == project_mapping.project_id,
            )
        ) if project_mapping else None
        if project is None or project.status != "active" or membership is None:
            raise HTTPException(409, "The simulated project mapping is unavailable")

        source_key = compute_source_event_key(config.calendar_id, MOCK_EVENT_ID)
        if session.scalar(
            select(TimeEntrySourceLink).where(
                TimeEntrySourceLink.integration_id == config.integration_id,
                TimeEntrySourceLink.source_event_key == source_key,
            )
        ):
            raise HTTPException(409, "This simulated Calendar event is already confirmed")

        revision_key = compute_revision_key(
            config.calendar_id, MOCK_EVENT_ID, MOCK_UPDATED_AT
        )
        existing = session.scalar(
            select(IntegrationSuggestion).where(
                IntegrationSuggestion.integration_id == config.integration_id,
                IntegrationSuggestion.source_event_key == source_key,
            )
        )
        if existing is not None:
            return {"suggestion_id": existing.id, "created": False, "mode": "simulated"}

        now = _utcnow()
        suggestion = IntegrationSuggestion(
            id=str(uuid4()),
            integration_id=config.integration_id,
            source_event_key=source_key,
            current_revision_key=revision_key,
            actor_id=actor.id,
            project_id=project.id,
            person_ref=person.person_ref,
            project_code=project_mapping.project_code,
            work_date=(now - timedelta(days=1)).date(),
            duration_minutes=90,
            description="Prepared fictional customer workshop",
            status="suggested",
            expires_at=now + timedelta(days=14),
        )
        session.add(suggestion)
        session.add(
            IntegrationSuggestionRevision(
                integration_id=config.integration_id,
                suggestion_id=suggestion.id,
                revision_key=revision_key,
                event_updated_at=datetime.fromisoformat(
                    MOCK_UPDATED_AT.replace("Z", "+00:00")
                ).replace(tzinfo=None),
            )
        )
        session.add(
            AuditEvent(
                actor_id=actor.id,
                action="integration_mock_suggestion_created",
                resource_type="integration_suggestion",
                resource_id=suggestion.id,
                details='{"fixture":"simulated_calendar_v1"}',
            )
        )
        session.commit()
        return {"suggestion_id": suggestion.id, "created": True, "mode": "simulated"}
