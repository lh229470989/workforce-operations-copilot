"""Pydantic mirrors of the public v1 integration JSON Schemas."""

import re
import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


LOWER_REF_PATTERN = re.compile(r"^[a-z0-9-]{3,64}$")
PROJECT_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{2,32}$")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
SECRET_MARKER_PATTERN = re.compile(
    r"\b(?:api[_-]?key|authorization|bearer|client[_-]?secret|password|secret|token)\b",
    re.IGNORECASE,
)
HTML_PATTERN = re.compile(r"<[^>]*>")
RFC3339_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _contains_control(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _require_safe_text(value: str, *, reject_secret_markers: bool = False) -> str:
    if _contains_control(value):
        raise ValueError("control characters are not allowed")
    if reject_secret_markers and HTML_PATTERN.search(value):
        raise ValueError("HTML is not allowed")
    if reject_secret_markers and SECRET_MARKER_PATTERN.search(value):
        raise ValueError("secret markers are not allowed")
    return value


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must use UTC")
    return value


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkEventV1(StrictContractModel):
    schema_version: Literal["1.0"]
    source: Literal["google_calendar"]
    source_account_ref: Annotated[str, Field(pattern=LOWER_REF_PATTERN.pattern)]
    calendar_id: Annotated[str, Field(min_length=1, max_length=255)]
    event_id: Annotated[str, Field(min_length=1, max_length=255)]
    event_updated_at: datetime
    person_ref: Annotated[str, Field(pattern=LOWER_REF_PATTERN.pattern)]
    project_code: Annotated[str, Field(pattern=PROJECT_CODE_PATTERN.pattern)]
    work_date: date
    duration_minutes: Annotated[int, Field(strict=True, ge=15, le=1440, multiple_of=15)]
    description: Annotated[str, Field(min_length=1, max_length=200)]

    @field_validator("calendar_id", "event_id")
    @classmethod
    def validate_identifier_text(cls, value: str) -> str:
        return _require_safe_text(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _require_safe_text(value, reject_secret_markers=True)

    @field_validator("event_updated_at")
    @classmethod
    def validate_updated_at(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @field_validator("event_updated_at", mode="before")
    @classmethod
    def require_utc_timestamp_text(cls, value: object) -> object:
        if not isinstance(value, str) or RFC3339_UTC_PATTERN.fullmatch(value) is None:
            raise ValueError("timestamp must be RFC 3339 UTC text ending in Z")
        return value

    @field_validator("work_date", mode="before")
    @classmethod
    def require_iso_date_text(cls, value: object) -> object:
        if not isinstance(value, str) or ISO_DATE_PATTERN.fullmatch(value) is None:
            raise ValueError("work_date must be ISO date text")
        return value

    @field_serializer("event_updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ConfirmedResultV1(StrictContractModel):
    time_entry_id: Annotated[int, Field(strict=True, ge=1)]
    person_display_name: Annotated[str, Field(min_length=1, max_length=100)]
    project_display_name: Annotated[str, Field(min_length=1, max_length=100)]
    work_date: date
    hours: Annotated[
        Decimal,
        Field(strict=False, gt=0, le=24, multiple_of=Decimal("0.25"), decimal_places=2),
    ]
    status: Literal["draft", "submitted", "approved", "rejected"]

    @field_validator("person_display_name", "project_display_name")
    @classmethod
    def validate_display_text(cls, value: str) -> str:
        return _require_safe_text(value)

    @field_validator("hours", mode="before")
    @classmethod
    def require_canonical_hours(cls, value: object) -> object:
        if not isinstance(value, str) or not re.fullmatch(
            r"(?:0\.(?:25|50|75)|(?:[1-9]|1[0-9]|2[0-3])\.(?:00|25|50|75)|24\.00)",
            value,
        ):
            raise ValueError("hours must be a canonical quarter-hour decimal string")
        return value

    @field_validator("work_date", mode="before")
    @classmethod
    def require_iso_date_text(cls, value: object) -> object:
        if not isinstance(value, str) or ISO_DATE_PATTERN.fullmatch(value) is None:
            raise ValueError("work_date must be ISO date text")
        return value

    @field_serializer("hours")
    def serialize_hours(self, value: Decimal) -> str:
        return f"{value:.2f}"


class ConfirmedEventV1(StrictContractModel):
    schema_version: Literal["1.0"]
    event_type: Literal["time_entry.confirmed"]
    event_id: UUID
    occurred_at: datetime
    request_id: Annotated[str, Field(pattern=REQUEST_ID_PATTERN.pattern)]
    result: ConfirmedResultV1

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @field_validator("occurred_at", mode="before")
    @classmethod
    def require_utc_timestamp_text(cls, value: object) -> object:
        if not isinstance(value, str) or RFC3339_UTC_PATTERN.fullmatch(value) is None:
            raise ValueError("timestamp must be RFC 3339 UTC text ending in Z")
        return value

    @field_serializer("occurred_at")
    def serialize_occurred_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
