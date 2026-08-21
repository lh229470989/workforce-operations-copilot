"""Persistent notification claim ledger and simulated delivery preview."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from time import time
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from starlette.responses import JSONResponse

from ..auth import ActorDep, SessionDep
from ..models import (
    IntegrationNonce,
    IntegrationOutbox,
    IntegrationSuggestion,
    NotificationDelivery,
)
from .config import IngestIntegrationConfig
from .security import MAX_BODY_BYTES, validate_timestamp, verify_body_signature


CALLBACK_INTEGRATION_ID = "n8n-notification-v1"
CLAIM_LEASE_MINUTES = 15


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_ref: str = Field(pattern=r"^[a-z0-9-]{3,64}$")


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_attempt_id: UUID
    status: Literal["delivered", "failed", "delivery_unknown"]


def _error(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"schema_version": "1.0", "code": code},
    )


async def _authenticate(
    request: Request,
    *,
    path: str,
    config: IngestIntegrationConfig,
    session,
) -> tuple[bytes | None, JSONResponse | None]:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                return None, _error(413, "payload_too_large")
        except ValueError:
            return None, _error(400, "invalid_content_length")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return None, _error(413, "payload_too_large")
    if (
        request.headers.get("X-Acme-Integration-Id")
        != CALLBACK_INTEGRATION_ID
        or not config.notification_callback_secrets
    ):
        return None, _error(403, "integration_disabled")
    timestamp_text = request.headers.get("X-Acme-Timestamp", "")
    nonce = request.headers.get("X-Acme-Nonce", "")
    signature = request.headers.get("X-Acme-Signature", "")
    try:
        timestamp = int(timestamp_text)
        validate_timestamp(timestamp, now=int(time()))
        valid = verify_body_signature(
            signature,
            config.notification_callback_secrets,
            timestamp=timestamp,
            nonce=nonce,
            method="POST",
            path=path,
            body=body,
        )
    except (TypeError, ValueError):
        return None, _error(401, "invalid_signature")
    if not valid:
        return None, _error(401, "invalid_signature")

    now = _utcnow()
    nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
    session.execute(delete(IntegrationNonce).where(IntegrationNonce.expires_at < now))
    session.add(
        IntegrationNonce(
            integration_id=CALLBACK_INTEGRATION_ID,
            nonce_hash=nonce_hash,
            expires_at=now + timedelta(minutes=10),
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, _error(401, "replayed_nonce")
    return body, None


def register_notification_routes(
    app: FastAPI, config: IngestIntegrationConfig
) -> None:
    @app.get("/integration-notifications/preview", tags=["integrations"])
    def notification_preview(session: SessionDep, actor: ActorDep) -> list[dict]:
        rows = session.execute(
            select(IntegrationOutbox, IntegrationSuggestion)
            .join(
                IntegrationSuggestion,
                IntegrationSuggestion.id == IntegrationOutbox.suggestion_id,
            )
            .where(IntegrationSuggestion.actor_id == actor.id)
            .order_by(IntegrationOutbox.created_at.desc())
        ).all()
        return [
            {
                "delivery_mode": "simulated",
                "event_id": outbox.event_id,
                "status": outbox.status,
                "event": json.loads(outbox.payload),
            }
            for outbox, _ in rows
        ]

    @app.post(
        "/api/v1/integrations/notifications/{event_id}:claim",
        tags=["integrations"],
    )
    async def claim_notification(event_id: str, request: Request) -> JSONResponse:
        path = f"/api/v1/integrations/notifications/{event_id}:claim"
        with request.app.state.session_factory() as session:
            raw, auth_error = await _authenticate(
                request, path=path, config=config, session=session
            )
            if auth_error:
                return auth_error
            try:
                body = ClaimRequest.model_validate_json(raw)
                UUID(event_id)
            except (ValidationError, ValueError):
                return _error(422, "invalid_claim")
            outbox = session.get(IntegrationOutbox, event_id)
            if outbox is None:
                return _error(404, "event_not_found")

            now = _utcnow()
            expired = list(
                session.scalars(
                    select(NotificationDelivery).where(
                        NotificationDelivery.event_id == event_id,
                        NotificationDelivery.status == "sending",
                        NotificationDelivery.claim_expires_at < now,
                    )
                )
            )
            for delivery in expired:
                delivery.status = "delivery_unknown"
                delivery.completed_at = now
                outbox.status = "delivery_unknown"
            existing = session.scalar(
                select(NotificationDelivery)
                .where(NotificationDelivery.event_id == event_id)
                .order_by(NotificationDelivery.attempt_no.desc())
            )
            if existing is not None:
                session.commit()
                return JSONResponse(
                    content={
                        "schema_version": "1.0",
                        "claim_granted": False,
                        "status": existing.status,
                    }
                )
            if outbox.status != "queued":
                session.commit()
                return JSONResponse(
                    content={
                        "schema_version": "1.0",
                        "claim_granted": False,
                        "status": outbox.status,
                    }
                )
            attempt = NotificationDelivery(
                delivery_attempt_id=str(uuid4()),
                event_id=event_id,
                attempt_no=1,
                channel_ref_hash=hashlib.sha256(body.channel_ref.encode()).hexdigest(),
                status="sending",
                claim_expires_at=now + timedelta(minutes=CLAIM_LEASE_MINUTES),
            )
            session.add(attempt)
            outbox.status = "sending"
            outbox.attempt_count = 1
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return JSONResponse(
                    content={
                        "schema_version": "1.0",
                        "claim_granted": False,
                        "status": "already_claimed",
                    }
                )
            return JSONResponse(
                content={
                    "schema_version": "1.0",
                    "claim_granted": True,
                    "delivery_attempt_id": attempt.delivery_attempt_id,
                    "lease_expires_at": attempt.claim_expires_at.isoformat() + "Z",
                }
            )

    @app.post(
        "/api/v1/integrations/notifications/{event_id}:complete",
        tags=["integrations"],
    )
    async def complete_notification(event_id: str, request: Request) -> JSONResponse:
        path = f"/api/v1/integrations/notifications/{event_id}:complete"
        with request.app.state.session_factory() as session:
            raw, auth_error = await _authenticate(
                request, path=path, config=config, session=session
            )
            if auth_error:
                return auth_error
            try:
                body = CompleteRequest.model_validate_json(raw)
                UUID(event_id)
            except (ValidationError, ValueError):
                return _error(422, "invalid_completion")
            attempt = session.get(
                NotificationDelivery, str(body.delivery_attempt_id)
            )
            outbox = session.get(IntegrationOutbox, event_id)
            if (
                attempt is None
                or outbox is None
                or attempt.event_id != event_id
                or attempt.status != "sending"
            ):
                return _error(409, "delivery_not_claimed")
            now = _utcnow()
            if attempt.claim_expires_at < now:
                attempt.status = "delivery_unknown"
                attempt.completed_at = now
                outbox.status = "delivery_unknown"
                session.commit()
                return _error(409, "claim_expired")
            attempt.status = body.status
            attempt.completed_at = now
            outbox.status = body.status
            session.commit()
            return JSONResponse(
                content={
                    "schema_version": "1.0",
                    "event_id": event_id,
                    "status": body.status,
                }
            )
