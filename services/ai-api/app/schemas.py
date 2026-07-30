from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

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
        "pending_team",
        "policy_question",
        "draft_time_entry",
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
