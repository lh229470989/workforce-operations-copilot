from datetime import date
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from .core_client import CoreAPIClient
from .knowledge_base import PolicyKnowledgeBase
from .planner import Planner
from .query_registry import ReadQueryRegistry, resolve_project, tool_event
from .schemas import (
    AgentPlan,
    ChatResponse,
    ConfirmationCard,
    ExecutionResult,
    PlannerContext,
)


class AgentState(TypedDict, total=False):
    message: str
    actor_id: int
    planner_context: PlannerContext
    plan: AgentPlan
    result: ExecutionResult
    response: ChatResponse


def build_agent(
    planner: Planner,
    core: CoreAPIClient,
    *,
    mode: str,
    knowledge_base: PolicyKnowledgeBase | None = None,
    today_provider: Callable[[], date] = date.today,
):
    read_queries = ReadQueryRegistry(core)

    async def plan_node(state: AgentState) -> dict[str, AgentPlan]:
        return {
            "plan": await planner.plan(
                state["message"],
                today_provider(),
                state["actor_id"],
                state.get("planner_context"),
            )
        }

    async def execute_node(state: AgentState) -> dict[str, ExecutionResult]:
        plan = state["plan"]
        actor_id = state["actor_id"]
        if plan.intent in {"capabilities", "unknown"}:
            return {
                "result": ExecutionResult(
                    message=(
                        "I can show your identity, visible departments, employees, "
                        "projects and project members; list and summarize role-scoped "
                        "time entries; prepare monthly chart data; inspect pending "
                        "approvals; answer cited AcmeWorks policy questions; and "
                        "create a dry-run time-entry draft. I cannot "
                        "confirm writes or approve entries."
                        if plan.intent == "capabilities"
                        else "I could not map that request safely. Ask for your profile, "
                        "departments, employees, projects, project members, time-entry "
                        "records, status summary, hours, monthly chart data, pending "
                        "approvals, a policy question, or provide an exact project, "
                        "date, hours, and description for a draft."
                    )
                )
            }

        if plan.intent == "policy_question":
            retrieval = (
                knowledge_base.search(state["message"])
                if knowledge_base is not None
                else None
            )
            if retrieval is None:
                return {
                    "result": ExecutionResult(
                        message=(
                            "I could not find enough evidence in the authored "
                            "AcmeWorks policies to answer that safely."
                        ),
                        tool_events=[
                            tool_event(
                                "retrieve_policy",
                                {"query": state["message"]},
                                {"matches": 0},
                            )
                        ],
                    )
                }
            return {
                "result": ExecutionResult(
                    message=retrieval.answer,
                    citations=retrieval.citations,
                    tool_events=[
                        tool_event(
                            "retrieve_policy",
                            {"query": state["message"]},
                            {
                                "matches": len(retrieval.citations),
                                "confidence": retrieval.confidence,
                                "source_ids": [
                                    citation.source_id
                                    for citation in retrieval.citations
                                ],
                            },
                        )
                    ],
                )
            }

        if read_queries.handles(plan.intent):
            return {"result": await read_queries.execute(plan, actor_id)}

        if plan.intent == "draft_time_entry":
            events = []
            missing = [
                name
                for name, value in (
                    ("project", plan.project_id or plan.project_name),
                    ("work_date", plan.work_date),
                    ("hours", plan.hours),
                    ("description", plan.description),
                )
                if value is None
            ]
            if missing:
                return {
                    "result": ExecutionResult(
                        message=(
                            "I need exact values before creating a dry-run draft: "
                            + ", ".join(missing)
                            + "."
                        )
                    )
                }
            projects = await core.list_projects(actor_id)
            events.append(tool_event("list_projects", {}, projects))
            project = resolve_project(projects, plan)
            if project is None:
                return {
                    "result": ExecutionResult(
                        message="That project is not available in your authorized scope.",
                        tool_events=events,
                    )
                }
            payload = {
                "project_id": project["id"],
                "work_date": plan.work_date.isoformat(),
                "hours": str(plan.hours),
                "description": plan.description,
            }
            preview = await core.dry_run_time_entry(actor_id, payload)
            events.append(tool_event("dry_run_time_entry", payload, preview))
            card = ConfirmationCard(
                action=preview["action"],
                preview=preview["preview"],
                confirmation_token=preview["confirmation_token"],
                expires_at=preview["expires_at"],
                confirm_path=(
                    f"/actions/{preview['confirmation_token']}/confirm"
                ),
            )
            return {
                "result": ExecutionResult(
                    message=(
                        "I prepared a dry-run draft. Review the confirmation card; "
                        "nothing has been added to your time entries."
                    ),
                    tool_events=events,
                    data=preview["preview"],
                    confirmation=card,
                )
            }

        return {
            "result": ExecutionResult(message="No supported operation was selected.")
        }

    async def compose_node(state: AgentState) -> dict[str, ChatResponse]:
        result = state["result"]
        return {
            "response": ChatResponse(
                message=result.message,
                mode=mode,
                tool_events=result.tool_events,
                citations=result.citations,
                data=result.data,
                confirmation=result.confirmation,
            )
        }

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("compose", compose_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "compose")
    graph.add_edge("compose", END)
    return graph.compile()
