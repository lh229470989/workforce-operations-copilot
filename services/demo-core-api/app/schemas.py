from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DepartmentOut(ORMModel):
    id: int
    name: str
    code: str


class EmployeeOut(ORMModel):
    id: int
    name: str
    email: str
    role: Literal["employee", "manager", "admin"]
    title: str
    department_id: int
    manager_id: int | None


class ProjectOut(ORMModel):
    id: int
    name: str
    code: str
    description: str
    status: str
    department_id: int


class ProjectMemberOut(ORMModel):
    id: int
    project_id: int
    employee_id: int
    project_role: str


class TimeEntryOut(ORMModel):
    id: int
    employee_id: int
    project_id: int
    work_date: date
    hours: Decimal
    description: str
    status: Literal["draft", "submitted", "approved", "rejected"]
    created_at: datetime
    updated_at: datetime


class ApprovalOut(ORMModel):
    id: int
    time_entry_id: int
    actor_id: int
    decision: Literal["approved", "rejected"]
    comment: str | None
    created_at: datetime


class TimeEntryDraftRequest(BaseModel):
    employee_id: int | None = None
    project_id: int
    work_date: date
    hours: Decimal = Field(gt=0, le=24, max_digits=4, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)


class TimeEntryBatchDraftRequest(BaseModel):
    """A bounded batch that remains a single explicit confirmation action."""

    entries: list[TimeEntryDraftRequest] = Field(min_length=1, max_length=10)


class TimeEntryUpdateRequest(BaseModel):
    """Editable fields for an existing draft; status changes use dedicated actions."""

    project_id: int | None = Field(default=None, ge=1)
    work_date: date | None = None
    hours: Decimal | None = Field(
        default=None, gt=0, le=24, max_digits=4, decimal_places=2
    )
    description: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        return self


class TimeEntrySuggestionOut(BaseModel):
    """A non-authoritative suggestion grounded in one personal recent entry."""

    project_id: int
    project_name: str
    target_date: date
    suggested_hours: Decimal
    suggested_description: str
    based_on_entry_id: int
    based_on_date: date


class SafeAnalyticsQuery(BaseModel):
    """A declarative analytics request; callers can never supply SQL text."""

    dimension: Literal["project", "status", "employee", "work_date", "month"]
    metric: Literal["hours", "entry_count"]
    start_date: date | None = None
    end_date: date | None = None
    status: Literal["draft", "submitted", "approved", "rejected"] | None = None
    project_id: int | None = Field(default=None, ge=1)
    employee_id: int | None = Field(default=None, ge=1)
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=20, ge=1, le=50)


class ApprovalDryRunRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=500)


class ApprovalBatchDryRunRequest(ApprovalDryRunRequest):
    entry_ids: list[int] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def require_unique_entries(self):
        if len(set(self.entry_ids)) != len(self.entry_ids):
            raise ValueError("entry_ids must be unique")
        return self


class DryRunResponse(BaseModel):
    dry_run: Literal[True] = True
    action: str
    preview: dict
    confirmation_token: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_expires_at(self, value: datetime) -> str:
        """Expose unambiguous UTC so browsers do not assume local time."""

        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
        return aware.astimezone(UTC).isoformat().replace("+00:00", "Z")


class ConfirmationRequest(BaseModel):
    confirm: Literal[True]


class ConfirmationResponse(BaseModel):
    dry_run: Literal[False] = False
    action: str
    result: dict


class ProjectHoursStat(BaseModel):
    project_id: int
    project_name: str
    hours: Decimal


class MonthlyHoursStat(BaseModel):
    month: str
    hours: Decimal


class SummaryStat(BaseModel):
    total_hours: Decimal
    draft_hours: Decimal
    submitted_hours: Decimal
    approved_hours: Decimal
    rejected_hours: Decimal


class IntegrationSuggestionOut(BaseModel):
    id: str
    source_label: str
    status: Literal["suggested", "previewed", "confirmed", "expired", "superseded"]
    person_ref: str
    project_id: int
    project_code: str
    project_name: str
    work_date: date
    hours: Decimal
    description: str
    expires_at: datetime


class IntegrationSuggestionPrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int = Field(ge=1)
    work_date: date
    hours: Decimal = Field(gt=0, le=24, max_digits=4, decimal_places=2)
    description: str = Field(min_length=1, max_length=200)
