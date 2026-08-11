"""Build trusted user context and resolve structured conversation references."""

from .core_client import CoreAPIClient
from .query_registry import READ_INTENTS
from .schemas import AgentPlan, ContextSummary, PlanFieldResolution, PlannerContext
from .session_memory import SessionRecord

INHERITABLE_READ_FIELDS = (
    "project_id",
    "project_name",
    "entry_status",
    "start_date",
    "end_date",
)


async def build_planner_context(
    core: CoreAPIClient,
    actor_id: int,
    session: SessionRecord,
    preferences: dict[str, object] | None = None,
) -> PlannerContext:
    """Combine short conversation history with fresh, authorized Core data."""

    # Authorization-sensitive attributes are deliberately refreshed for every
    # request. Session history must never become a stale source of truth for a
    # user's role, department, projects, or visible time entries.
    actor = await core.get_me(actor_id)
    departments = await core.list_departments(actor_id)
    projects = await core.list_projects(actor_id)
    recent_entries = (await core.list_time_entries(actor_id))[:5]
    supplied_preferences = preferences or {}
    preferred_id = supplied_preferences.get("preferred_project_id")
    preferred_project = next(
        (project for project in projects if project["id"] == preferred_id), None
    )
    return PlannerContext(
        session_id=session.session_id,
        turns=session.turns,
        actor=actor,
        departments=departments,
        projects=projects,
        recent_time_entries=recent_entries,
        preferences={
            "history_enabled": supplied_preferences.get("history_enabled", True),
            "preferred_language": supplied_preferences.get(
                "preferred_language", "auto"
            ),
            # Re-resolve the preference against current authorized projects;
            # stale preferences never grant project visibility.
            "preferred_project": (
                {"id": preferred_project["id"], "name": preferred_project["name"]}
                if preferred_project
                else None
            ),
        },
    )


def summarize_context(context: PlannerContext) -> ContextSummary:
    """Return a small, non-sensitive description for the chat UI."""

    return ContextSummary(
        turn_count=len(context.turns) + 1,
        actor_role=str(context.actor["role"]),
        department_names=[
            str(department["name"]) for department in context.departments
        ],
        recent_project_names=context.recent_project_names,
    )


def resolve_plan_context(
    plan: AgentPlan, context: PlannerContext | None
) -> AgentPlan:
    """Resolve planner-declared references under deterministic server policy."""

    if context is None:
        return _record_current_fields(plan)

    updates: dict[str, object] = {}
    resolutions = _current_field_resolutions(plan)

    # Attribute references are resolved from fresh Core data, never from
    # untrusted prose stored in the conversation.
    if plan.project_reference == "recent" and context.recent_project_names:
        updates["project_name"] = context.recent_project_names[0]
        resolutions = _replace_resolution(
            resolutions, "project_name", "actor_context"
        )

    last_plan = context.last_plan
    relation_uses_history = plan.conversation_relation in {
        "refine_previous",
        "switch_subject",
    }

    # A planner cannot make a write safer by asking to inherit missing values.
    # History is eligible only when both the previous and resolved intents are
    # registered read operations.
    if (
        relation_uses_history
        and last_plan is not None
        and last_plan.intent in READ_INTENTS
        and plan.intent in READ_INTENTS | {"unknown"}
    ):
        if plan.intent == "unknown":
            updates["intent"] = last_plan.intent
        for field_name in plan.inherit_fields:
            if field_name not in INHERITABLE_READ_FIELDS:
                continue
            if getattr(plan, field_name) is not None or field_name in updates:
                continue
            previous = getattr(last_plan, field_name)
            if previous is not None:
                updates[field_name] = previous
                resolutions = _replace_resolution(
                    resolutions, field_name, "previous_turn"
                )

    updates["field_resolutions"] = resolutions
    return plan.model_copy(update=updates)


def infer_local_conversation_relation(
    plan: AgentPlan, context: PlannerContext | None
) -> AgentPlan:
    """Provide a deterministic fallback from parsed slots, not phrase matching."""

    if context is None or context.last_plan is None:
        return plan
    if context.last_plan.intent not in READ_INTENTS or plan.intent != "unknown":
        return plan

    # In local mode an otherwise unknown request containing only a new project
    # is a subject switch; an unknown request containing query filters refines
    # the previous read. Semantic planners declare these relations directly.
    if plan.project_name is not None:
        return plan.model_copy(
            update={
                "conversation_relation": "switch_subject",
                "inherit_fields": [
                    "entry_status",
                    "start_date",
                    "end_date",
                ],
            }
        )
    if any(
        value is not None
        for value in (plan.entry_status, plan.start_date, plan.end_date)
    ):
        return plan.model_copy(
            update={
                "conversation_relation": "refine_previous",
                "inherit_fields": [
                    "project_id",
                    "project_name",
                    "entry_status",
                    "start_date",
                    "end_date",
                ],
            }
        )
    return plan


def _record_current_fields(plan: AgentPlan) -> AgentPlan:
    return plan.model_copy(
        update={"field_resolutions": _current_field_resolutions(plan)}
    )


def _current_field_resolutions(plan: AgentPlan) -> list[PlanFieldResolution]:
    return [
        PlanFieldResolution(field=field_name, source="current_message")
        for field_name in INHERITABLE_READ_FIELDS
        if getattr(plan, field_name) is not None
    ]


def _replace_resolution(
    resolutions: list[PlanFieldResolution],
    field_name: str,
    source: str,
) -> list[PlanFieldResolution]:
    retained = [
        item for item in resolutions if item.field != field_name
    ]
    retained.append(PlanFieldResolution(field=field_name, source=source))
    return retained
