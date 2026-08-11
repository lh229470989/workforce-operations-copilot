from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

PlanFieldName = Literal[
    "project_id",
    "project_name",
    "entry_status",
    "start_date",
    "end_date",
]


class PlanFieldResolution(BaseModel):
    """Explain where a resolved plan field came from."""

    field: PlanFieldName
    source: Literal["current_message", "previous_turn", "actor_context"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: UUID | None = None


class PreferenceUpdateRequest(BaseModel):
    history_enabled: bool | None = None
    preferred_language: Literal["auto", "en", "zh"] | None = None
    preferred_project_id: int | None = Field(default=None, ge=1)
    clear_preferred_project: bool = False
    response_detail: Literal["concise", "standard", "detailed"] | None = None
    report_format: Literal["summary", "csv"] | None = None

    @model_validator(mode="after")
    def require_one_change(self):
        if (
            self.history_enabled is None
            and self.preferred_language is None
            and self.preferred_project_id is None
            and not self.clear_preferred_project
            and self.response_detail is None
            and self.report_format is None
        ):
            raise ValueError("At least one preference change is required")
        return self


class PreferenceConfirmRequest(BaseModel):
    confirm: Literal[True]


class TimeEntryDraftItem(BaseModel):
    """One exact item proposed as part of a batch dry-run."""

    project_id: int | None = None
    project_name: str | None = None
    work_date: date | None = None
    hours: Decimal | None = Field(default=None, gt=0, le=24)
    description: str | None = Field(default=None, max_length=500)


class AnalysisStep(BaseModel):
    """One bounded, read-only slice in a comparison plan."""

    label: str = Field(min_length=1, max_length=80)
    project_id: int | None = Field(default=None, ge=1)
    project_name: str | None = Field(default=None, max_length=80)
    entry_status: Literal["draft", "submitted", "approved", "rejected"] | None = None
    start_date: date | None = None
    end_date: date | None = None


class AnalyticsQuerySpec(BaseModel):
    """Declarative read-only analytics compiled by Core API, never raw SQL."""

    dimension: Literal["project", "status", "employee", "work_date", "month"]
    metric: Literal["hours", "entry_count"]
    start_date: date | None = None
    end_date: date | None = None
    entry_status: Literal["draft", "submitted", "approved", "rejected"] | None = None
    project_id: int | None = Field(default=None, ge=1)
    project_name: str | None = Field(default=None, max_length=80)
    employee_id: int | None = Field(default=None, ge=1)
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=20, ge=1, le=50)


class AgentPlan(BaseModel):
    intent: Literal[
        "current_user",
        "list_departments",
        "list_employees",
        "list_projects",
        "project_members",
        "time_entries",
        "hours_by_project",
        "summary",
        "monthly_chart",
        "weekly_report",
        "compare_analysis",
        "safe_sql_analysis",
        "pending_team",
        "policy_question",
        "suggest_time_entries",
        "draft_time_entry",
        "draft_time_entries_batch",
        "decide_time_entry",
        "decide_time_entries",
        "manage_time_entry",
        "greeting",
        "general_chat",
        "capabilities",
        "unknown",
    ]
    conversation_relation: Literal[
        "independent",
        "refine_previous",
        "switch_subject",
        "use_actor_context",
    ] = "independent"
    inherit_fields: list[PlanFieldName] = Field(default_factory=list)
    project_reference: Literal["recent"] | None = None
    field_resolutions: list[PlanFieldResolution] = Field(default_factory=list)
    project_id: int | None = None
    project_name: str | None = None
    entry_status: Literal["draft", "submitted", "approved", "rejected"] | None = (
        None
    )
    limit: int | None = Field(default=None, ge=1, le=50)
    start_date: date | None = None
    end_date: date | None = None
    work_date: date | None = None
    hours: Decimal | None = Field(default=None, gt=0, le=24)
    description: str | None = Field(default=None, max_length=500)
    time_entry_id: int | None = Field(default=None, ge=1)
    time_entry_ids: list[int] = Field(default_factory=list, max_length=20)
    approval_decision: Literal["approved", "rejected"] | None = None
    approval_comment: str | None = Field(default=None, max_length=500)
    lifecycle_action: Literal["update", "delete", "submit", "withdraw"] | None = None
    batch_entries: list[TimeEntryDraftItem] = Field(
        default_factory=list, max_length=10
    )
    analysis_steps: list[AnalysisStep] = Field(
        default_factory=list, min_length=0, max_length=4
    )
    analytics_query: AnalyticsQuerySpec | None = None

    @field_validator("inherit_fields", "time_entry_ids", mode="before")
    @classmethod
    def normalize_empty_lists(cls, value: Any) -> Any:
        """Normalize provider-specific empty renderings for optional lists."""

        return [] if value in ({}, "", None) else value

    @field_validator(
        "approval_decision", "lifecycle_action", mode="before"
    )
    @classmethod
    def normalize_empty_optional_literals(cls, value: Any) -> Any:
        """DashScope may render an unused optional enum as an empty string."""

        return None if value in ({}, "", None) else value

    @field_validator("field_resolutions", mode="before")
    @classmethod
    def normalize_empty_field_resolutions(cls, value: Any) -> Any:
        """Accept a provider's empty-object rendering as an empty list.

        Field resolutions are recalculated by trusted application code after
        planning, so normalizing this empty value cannot grant capabilities.
        """

        return [] if value in ({}, None) else value

    @field_validator("batch_entries", mode="before")
    @classmethod
    def normalize_empty_batch_entries(cls, value: Any) -> Any:
        return [] if value in ({}, None) else value

    @field_validator("analysis_steps", mode="before")
    @classmethod
    def normalize_empty_analysis_steps(cls, value: Any) -> Any:
        return [] if value in ({}, None) else value

    @field_validator("analytics_query", mode="before")
    @classmethod
    def normalize_empty_analytics_query(cls, value: Any) -> Any:
        return None if value in ({}, None) else value

    @field_validator("conversation_relation", mode="before")
    @classmethod
    def normalize_unknown_conversation_relation(cls, value: Any) -> Any:
        """Make provider-specific empty values safely independent.

        Only explicit allowlisted relations can inherit read filters. Any
        unknown rendering therefore receives the least-privileged default.
        """

        allowed = {
            "independent",
            "refine_previous",
            "switch_subject",
            "use_actor_context",
        }
        return (
            value
            if isinstance(value, str) and value in allowed
            else "independent"
        )


class ConversationTurn(BaseModel):
    """The minimal prior-turn data needed to resolve a follow-up safely."""

    user_message: str
    assistant_message: str
    plan: AgentPlan


class PlannerContext(BaseModel):
    """Short history plus authoritative actor data refreshed for this request."""

    session_id: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    actor: dict[str, Any]
    departments: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    recent_time_entries: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @property
    def last_plan(self) -> AgentPlan | None:
        return self.turns[-1].plan if self.turns else None

    @property
    def recent_project_names(self) -> list[str]:
        """Return distinct visible project names ordered by recent entry use."""

        project_names = {
            project["id"]: project["name"] for project in self.projects
        }
        names: list[str] = []
        for entry in self.recent_time_entries:
            name = project_names.get(entry["project_id"])
            if name and name not in names:
                names.append(name)
        return names


class ContextSummary(BaseModel):
    turn_count: int
    actor_role: str
    department_names: list[str]
    recent_project_names: list[str]


class ToolEvent(BaseModel):
    id: str
    name: str
    status: Literal["completed", "failed"] = "completed"
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None


class PolicyCitation(BaseModel):
    """A policy section used to ground an answer."""

    source_id: str
    title: str
    section: str
    path: str
    excerpt: str


class ConfirmationCard(BaseModel):
    action: str
    preview: dict[str, Any]
    confirmation_token: str
    expires_at: datetime
    confirm_path: str


class ChartData(BaseModel):
    type: Literal["bar"]
    title: str
    x_key: str
    series_key: str
    value_key: str
    rows: list[dict[str, Any]]


class ChatResponse(BaseModel):
    message: str
    mode: Literal["local", "openai"]
    session_id: str | None = None
    context: ContextSummary | None = None
    tool_events: list[ToolEvent] = Field(default_factory=list)
    citations: list[PolicyCitation] = Field(default_factory=list)
    data: Any = None
    confirmation: ConfirmationCard | None = None


class ExecutionResult(BaseModel):
    message: str
    tool_events: list[ToolEvent] = Field(default_factory=list)
    citations: list[PolicyCitation] = Field(default_factory=list)
    data: Any = None
    confirmation: ConfirmationCard | None = None
