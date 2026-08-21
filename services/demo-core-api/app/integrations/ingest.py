"""Signed WorkEvent ingestion that persists suggestions, never business writes."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from time import time
from uuid import uuid4

from fastapi import FastAPI, Request
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from ..models import (
    AuditEvent,
    Employee,
    IntegrationNonce,
    IntegrationPersonMapping,
    IntegrationProjectMapping,
    IntegrationSource,
    IntegrationSuggestion,
    IntegrationSuggestionRevision,
    Project,
    ProjectMember,
    TimeEntrySourceLink,
)
from .config import IngestIntegrationConfig, hash_reference
from .contracts import WorkEventV1
from .security import (
    MAX_BODY_BYTES,
    compute_idempotency_key,
    compute_revision_key,
    compute_source_event_key,
    validate_timestamp,
    verify_body_signature,
)


INGEST_PATH = "/api/v1/integrations/work-events:ingest"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
NONCE_WINDOW_MINUTES = 10
SUGGESTION_TTL_DAYS = 14


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    return supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else f"req_{uuid4().hex}"


def _error(status_code: int, code: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"schema_version": "1.0", "request_id": request_id, "code": code},
    )


def _response(suggestion: IntegrationSuggestion, *, duplicate: bool) -> dict:
    hours = Decimal(suggestion.duration_minutes) / Decimal(60)
    return {
        "schema_version": "1.0",
        "suggestion_id": suggestion.id,
        "status": suggestion.status,
        "duplicate": duplicate,
        "preview": {
            "person_ref": suggestion.person_ref,
            "project_code": suggestion.project_code,
            "work_date": suggestion.work_date.isoformat(),
            "hours": f"{hours:.2f}",
            "description": suggestion.description,
        },
    }


def register_ingest_routes(
    app: FastAPI, config: IngestIntegrationConfig
) -> None:
    @app.post(INGEST_PATH, tags=["integrations"])
    async def ingest_work_event(request: Request) -> JSONResponse:
        request_id = _request_id(request)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    return _error(413, "payload_too_large", request_id)
            except ValueError:
                return _error(400, "invalid_content_length", request_id)
        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return _error(413, "payload_too_large", request_id)

        integration_id = request.headers.get("X-Acme-Integration-Id", "")
        timestamp_text = request.headers.get("X-Acme-Timestamp", "")
        nonce = request.headers.get("X-Acme-Nonce", "")
        signature = request.headers.get("X-Acme-Signature", "")
        idempotency_key = request.headers.get("X-Acme-Idempotency-Key", "")
        if integration_id != config.integration_id:
            return _error(403, "integration_disabled", request_id)

        session_factory = request.app.state.session_factory
        with session_factory() as session:
            source = session.scalar(
                select(IntegrationSource).where(
                    IntegrationSource.integration_id == integration_id
                )
            )
            if (
                source is None
                or not source.enabled
                or not config.enabled
                or not config.verification_secrets
            ):
                return _error(403, "integration_disabled", request_id)
            try:
                timestamp = int(timestamp_text)
                validate_timestamp(timestamp, now=int(time()))
                valid_signature = verify_body_signature(
                    signature,
                    config.verification_secrets,
                    timestamp=timestamp,
                    nonce=nonce,
                    method="POST",
                    path=INGEST_PATH,
                    body=body,
                )
            except (TypeError, ValueError):
                return _error(401, "invalid_signature", request_id)
            if not valid_signature:
                return _error(401, "invalid_signature", request_id)

            now = _utcnow()
            nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
            session.execute(delete(IntegrationNonce).where(IntegrationNonce.expires_at < now))
            if session.scalar(
                select(IntegrationNonce).where(
                    IntegrationNonce.integration_id == integration_id,
                    IntegrationNonce.nonce_hash == nonce_hash,
                )
            ):
                session.rollback()
                return _error(401, "replayed_nonce", request_id)
            session.add(
                IntegrationNonce(
                    integration_id=integration_id,
                    nonce_hash=nonce_hash,
                    expires_at=now + timedelta(minutes=NONCE_WINDOW_MINUTES),
                )
            )
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                return _error(401, "replayed_nonce", request_id)
            session.commit()

            try:
                parsed = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError):
                session.rollback()
                return _error(400, "invalid_json", request_id)
            try:
                event = WorkEventV1.model_validate(parsed)
            except ValidationError:
                session.rollback()
                return _error(422, "invalid_work_event", request_id)

            if (
                hash_reference(event.source_account_ref)
                != source.source_account_ref_hash
                or hash_reference(event.calendar_id) != source.calendar_id_hash
            ):
                session.rollback()
                return _error(422, "mapping_not_found", request_id)

            person_mapping = session.scalar(
                select(IntegrationPersonMapping).where(
                    IntegrationPersonMapping.integration_id == integration_id,
                    IntegrationPersonMapping.person_ref == event.person_ref,
                )
            )
            project_mapping = session.scalar(
                select(IntegrationProjectMapping).where(
                    IntegrationProjectMapping.integration_id == integration_id,
                    IntegrationProjectMapping.project_code == event.project_code,
                )
            )
            if person_mapping is None or project_mapping is None:
                session.rollback()
                return _error(422, "mapping_not_found", request_id)
            actor = session.get(Employee, person_mapping.actor_id)
            project = session.get(Project, project_mapping.project_id)
            membership = session.scalar(
                select(ProjectMember).where(
                    ProjectMember.employee_id == person_mapping.actor_id,
                    ProjectMember.project_id == project_mapping.project_id,
                )
            )
            today = date.today()
            if (
                actor is None
                or project is None
                or project.status != "active"
                or membership is None
                or event.work_date < today - timedelta(days=config.past_days)
                or event.work_date > today + timedelta(days=config.future_days)
            ):
                session.rollback()
                return _error(422, "mapping_not_found", request_id)

            source_key = compute_source_event_key(event.calendar_id, event.event_id)
            revision_key = compute_revision_key(
                event.calendar_id,
                event.event_id,
                event.model_dump(mode="json")["event_updated_at"],
            )
            if idempotency_key != compute_idempotency_key(
                event.calendar_id,
                event.event_id,
                event.model_dump(mode="json")["event_updated_at"],
            ):
                session.rollback()
                return _error(422, "idempotency_key_mismatch", request_id)

            confirmed = session.scalar(
                select(TimeEntrySourceLink).where(
                    TimeEntrySourceLink.integration_id == integration_id,
                    TimeEntrySourceLink.source_event_key == source_key,
                )
            )
            if confirmed is not None:
                session.rollback()
                return _error(409, "source_already_confirmed", request_id)

            existing_revision = session.scalar(
                select(IntegrationSuggestionRevision).where(
                    IntegrationSuggestionRevision.integration_id == integration_id,
                    IntegrationSuggestionRevision.revision_key == revision_key,
                )
            )
            if existing_revision is not None:
                suggestion = session.get(
                    IntegrationSuggestion, existing_revision.suggestion_id
                )
                session.commit()
                return JSONResponse(
                    status_code=200,
                    content=_response(suggestion, duplicate=True),
                )

            suggestion = session.scalar(
                select(IntegrationSuggestion).where(
                    IntegrationSuggestion.integration_id == integration_id,
                    IntegrationSuggestion.source_event_key == source_key,
                )
            )
            created = suggestion is None
            if suggestion is None:
                suggestion = IntegrationSuggestion(
                    id=str(uuid4()),
                    integration_id=integration_id,
                    source_event_key=source_key,
                    current_revision_key=revision_key,
                    actor_id=actor.id,
                    project_id=project.id,
                    person_ref=event.person_ref,
                    project_code=event.project_code,
                    work_date=event.work_date,
                    duration_minutes=event.duration_minutes,
                    description=event.description,
                    status="suggested",
                    expires_at=now + timedelta(days=SUGGESTION_TTL_DAYS),
                )
                session.add(suggestion)
            else:
                suggestion.current_revision_key = revision_key
                suggestion.actor_id = actor.id
                suggestion.project_id = project.id
                suggestion.person_ref = event.person_ref
                suggestion.project_code = event.project_code
                suggestion.work_date = event.work_date
                suggestion.duration_minutes = event.duration_minutes
                suggestion.description = event.description
                suggestion.status = "suggested"
                suggestion.expires_at = now + timedelta(days=SUGGESTION_TTL_DAYS)
            session.add(
                IntegrationSuggestionRevision(
                    integration_id=integration_id,
                    suggestion_id=suggestion.id,
                    revision_key=revision_key,
                    event_updated_at=event.event_updated_at.replace(tzinfo=None),
                )
            )
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                raced_revision = session.scalar(
                    select(IntegrationSuggestionRevision).where(
                        IntegrationSuggestionRevision.integration_id == integration_id,
                        IntegrationSuggestionRevision.revision_key == revision_key,
                    )
                )
                if raced_revision is not None:
                    raced_suggestion = session.get(
                        IntegrationSuggestion, raced_revision.suggestion_id
                    )
                    return JSONResponse(
                        status_code=200,
                        content=_response(raced_suggestion, duplicate=True),
                    )
                return _error(503, "temporary_failure", request_id)
            session.add(
                AuditEvent(
                    actor_id=actor.id,
                    action=(
                        "integration_suggestion_created"
                        if created
                        else "integration_suggestion_updated"
                    ),
                    resource_type="integration_suggestion",
                    resource_id=suggestion.id,
                    details=json.dumps(
                        {
                            "request_id": request_id,
                            "integration_id": integration_id,
                            "schema_version": event.schema_version,
                            "source_event_key": source_key,
                            "revision_key": revision_key,
                            "status": suggestion.status,
                        }
                    ),
                )
            )
            session.commit()
            return JSONResponse(
                status_code=201,
                content=_response(suggestion, duplicate=False),
            )
