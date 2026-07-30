import asyncio
from datetime import date

from app.planner import LocalPlanner
from app.schemas import AgentPlan, ConversationTurn, PlannerContext


def planner_context(last_plan: AgentPlan) -> PlannerContext:
    return PlannerContext(
        session_id="demo-session",
        turns=[
            ConversationTurn(
                user_message="previous question",
                assistant_message="previous answer",
                plan=last_plan,
            )
        ],
        actor={"id": 3, "role": "employee"},
        departments=[],
        projects=[
            {"id": 1, "name": "Apollo"},
            {"id": 2, "name": "Beacon"},
        ],
        recent_time_entries=[{"project_id": 1}],
    )


def previous_hours_plan() -> AgentPlan:
    return AgentPlan(
        intent="hours_by_project",
        project_name="Apollo",
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 22),
    )


def test_local_subject_switch_uses_structured_slots_not_marker_phrases():
    plan = asyncio.run(
        LocalPlanner().plan(
            "Beacon?",
            date(2026, 7, 22),
            3,
            planner_context(previous_hours_plan()),
        )
    )

    assert plan.conversation_relation == "switch_subject"
    assert plan.intent == "hours_by_project"
    assert plan.project_name == "Beacon"
    assert plan.start_date == date(2026, 7, 20)
    assert {item.field: item.source for item in plan.field_resolutions} == {
        "project_name": "current_message",
        "start_date": "previous_turn",
        "end_date": "previous_turn",
    }


def test_filter_refinement_records_field_provenance():
    plan = asyncio.run(
        LocalPlanner().plan(
            "Only show submitted entries.",
            date(2026, 7, 22),
            3,
            planner_context(previous_hours_plan()),
        )
    )

    assert plan.conversation_relation == "refine_previous"
    assert plan.entry_status == "submitted"
    assert {item.field: item.source for item in plan.field_resolutions} == {
        "entry_status": "current_message",
        "project_name": "previous_turn",
        "start_date": "previous_turn",
        "end_date": "previous_turn",
    }


def test_write_plan_cannot_inherit_even_if_relation_is_requested():
    context = planner_context(previous_hours_plan())
    unsafe_request = AgentPlan(
        intent="draft_time_entry",
        conversation_relation="refine_previous",
        inherit_fields=["project_name", "start_date"],
    )

    from app.conversation_context import resolve_plan_context

    resolved = resolve_plan_context(unsafe_request, context)

    assert resolved.project_name is None
    assert resolved.start_date is None
    assert resolved.field_resolutions == []
