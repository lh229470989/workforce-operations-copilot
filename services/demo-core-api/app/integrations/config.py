"""Runtime-only configuration for signed integration ingress."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (
    IntegrationPersonMapping,
    IntegrationProjectMapping,
    IntegrationSource,
)


def hash_reference(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class IngestIntegrationConfig:
    integration_id: str = "n8n-calendar-v1"
    active_secret: bytes | None = None
    next_secret: bytes | None = None
    notification_callback_secret: bytes | None = None
    notification_callback_next_secret: bytes | None = None
    enabled: bool = False
    mode: str = "simulated"
    public_mock_enabled: bool = True
    source_account_ref: str = "google-test-account-01"
    calendar_id: str = "portfolio-work-calendar"
    person_mappings: dict[str, int] = field(
        default_factory=lambda: {"jamie-rivera": 3}
    )
    project_mappings: dict[str, int] = field(default_factory=lambda: {"APOLLO": 1})
    past_days: int = 90
    future_days: int = 30

    @classmethod
    def from_env(cls) -> "IngestIntegrationConfig":
        active = os.getenv("COPILOT_INGEST_HMAC_SECRET")
        next_secret = os.getenv("COPILOT_INGEST_HMAC_SECRET_NEXT")
        callback = os.getenv("COPILOT_NOTIFICATION_CALLBACK_HMAC_SECRET")
        callback_next = os.getenv(
            "COPILOT_NOTIFICATION_CALLBACK_HMAC_SECRET_NEXT"
        )
        public_mock_enabled = os.getenv(
            "COPILOT_PUBLIC_MOCK_ENABLED", "true"
        ).lower() == "true"
        if public_mock_enabled and (active or next_secret or callback or callback_next):
            raise RuntimeError(
                "Public simulated integration refuses real integration secrets"
            )
        return cls(
            active_secret=active.encode() if active else None,
            next_secret=next_secret.encode() if next_secret else None,
            notification_callback_secret=callback.encode() if callback else None,
            notification_callback_next_secret=(
                callback_next.encode() if callback_next else None
            ),
            enabled=bool(active),
            mode=os.getenv("COPILOT_INTEGRATION_MODE", "simulated"),
            public_mock_enabled=public_mock_enabled,
            source_account_ref=os.getenv(
                "COPILOT_SOURCE_ACCOUNT_REF", "google-test-account-01"
            ),
            calendar_id=os.getenv(
                "COPILOT_SOURCE_CALENDAR_ID", "portfolio-work-calendar"
            ),
        )

    @property
    def verification_secrets(self) -> tuple[bytes, ...]:
        return tuple(
            secret for secret in (self.active_secret, self.next_secret) if secret
        )

    @property
    def notification_callback_secrets(self) -> tuple[bytes, ...]:
        return tuple(
            secret
            for secret in (
                self.notification_callback_secret,
                self.notification_callback_next_secret,
            )
            if secret
        )


def sync_integration_config(
    session: Session, config: IngestIntegrationConfig
) -> None:
    source = session.scalar(
        select(IntegrationSource).where(
            IntegrationSource.integration_id == config.integration_id
        )
    )
    if source is None:
        source = IntegrationSource(integration_id=config.integration_id)
        session.add(source)
    source.source_account_ref_hash = hash_reference(config.source_account_ref)
    source.calendar_id_hash = hash_reference(config.calendar_id)
    source.enabled = config.enabled or (
        config.public_mock_enabled and config.mode == "simulated"
    )
    source.mode = config.mode

    person_delete = delete(IntegrationPersonMapping).where(
        IntegrationPersonMapping.integration_id == config.integration_id
    )
    if config.person_mappings:
        person_delete = person_delete.where(
            IntegrationPersonMapping.person_ref.not_in(config.person_mappings)
        )
    session.execute(person_delete)

    project_delete = delete(IntegrationProjectMapping).where(
        IntegrationProjectMapping.integration_id == config.integration_id
    )
    if config.project_mappings:
        project_delete = project_delete.where(
            IntegrationProjectMapping.project_code.not_in(config.project_mappings)
        )
    session.execute(project_delete)

    for person_ref, actor_id in config.person_mappings.items():
        mapping = session.scalar(
            select(IntegrationPersonMapping).where(
                IntegrationPersonMapping.integration_id == config.integration_id,
                IntegrationPersonMapping.person_ref == person_ref,
            )
        )
        if mapping is None:
            session.add(
                IntegrationPersonMapping(
                    integration_id=config.integration_id,
                    person_ref=person_ref,
                    actor_id=actor_id,
                )
            )
        else:
            mapping.actor_id = actor_id

    for project_code, project_id in config.project_mappings.items():
        mapping = session.scalar(
            select(IntegrationProjectMapping).where(
                IntegrationProjectMapping.integration_id == config.integration_id,
                IntegrationProjectMapping.project_code == project_code,
            )
        )
        if mapping is None:
            session.add(
                IntegrationProjectMapping(
                    integration_id=config.integration_id,
                    project_code=project_code,
                    project_id=project_id,
                )
            )
        else:
            mapping.project_id = project_id
    session.commit()
