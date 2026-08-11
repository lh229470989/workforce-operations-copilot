from datetime import date
from decimal import Decimal
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from .composer import LocalComposer, ResponseComposer
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
    composer: ResponseComposer | None = None,
    knowledge_base: PolicyKnowledgeBase | None = None,
    today_provider: Callable[[], date] = date.today,
):
    read_queries = ReadQueryRegistry(core)
    response_composer = composer or LocalComposer()

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
        if plan.intent in {
            "greeting",
            "general_chat",
            "capabilities",
            "unknown",
        }:
            is_chinese = any("\u4e00" <= char <= "\u9fff" for char in state["message"])
            messages = {
                "greeting": (
                    "你好！我是 Acme Copilot。你可以问我工时、项目、审批或 AcmeWorks 政策。"
                    if is_chinese
                    else "Hello! I'm Acme Copilot. Ask me about time, projects, approvals, or AcmeWorks policies."
                ),
                "general_chat": (
                    "我可以和你自然交流，也可以在服务端权限范围内帮助查询 AcmeWorks 演示数据。"
                    if is_chinese
                    else "I can chat with you and help with authorized AcmeWorks demo operations."
                ),
                "capabilities": (
                    "我可以查询你的身份、部门、员工、项目和工时，执行多个只读切片的对比分析，生成月度图表和周报，查看待审批记录，提供基于近期个人工时的填报建议，回答带引用的政策问题，并创建需要确认的工时或审批 dry-run；我不能代替你确认写入。"
                    if is_chinese
                    else "I can show role-scoped workforce data; run bounded multi-slice comparisons; create charts and weekly reports; suggest recent-work candidates; inspect approvals; answer cited policy questions; and create time-entry or approval dry-run proposals. I can never confirm a write."
                ),
                "unknown": (
                    "我还不能安全地把这个请求映射到已授权能力。你可以试试查询本周工时、可见项目或工时政策。"
                    if is_chinese
                    else "I could not map that request safely. Try asking about this week's hours, visible projects, or an AcmeWorks policy."
                ),
            }
            return {
                "result": ExecutionResult(
                    message=messages[plan.intent]
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
                                "evidence_coverage": retrieval.evidence_coverage,
                                "retrieval_mode": retrieval.retrieval_mode,
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

        if plan.intent == "safe_sql_analysis":
            spec = plan.analytics_query
            if spec is None:
                return {
                    "result": ExecutionResult(
                        message=(
                            "I cannot accept or generate raw SQL. Ask for a "
                            "read-only breakdown by project, status, employee, "
                            "date, or month instead."
                        )
                    )
                }
            events = []
            project_id = spec.project_id
            if spec.project_name is not None:
                projects = await core.list_projects(actor_id)
                events.append(tool_event("list_projects", {}, projects))
                project = resolve_project(
                    projects,
                    AgentPlan(
                        intent="time_entries", project_name=spec.project_name
                    ),
                )
                if project is None:
                    return {
                        "result": ExecutionResult(
                            message=(
                                "The requested analytics project is outside "
                                "your authorized scope."
                            ),
                            tool_events=events,
                        )
                    }
                project_id = project["id"]
            payload = {
                "dimension": spec.dimension,
                "metric": spec.metric,
                "start_date": (
                    spec.start_date.isoformat() if spec.start_date else None
                ),
                "end_date": spec.end_date.isoformat() if spec.end_date else None,
                "status": spec.entry_status,
                "project_id": project_id,
                "employee_id": spec.employee_id,
                "order": spec.order,
                "limit": spec.limit,
            }
            payload = {key: value for key, value in payload.items() if value is not None}
            result = await core.run_safe_analytics(actor_id, payload)
            events.append(tool_event("execute_safe_analytics_query", payload, result))
            return {
                "result": ExecutionResult(
                    message=(
                        f"The safe analytics compiler returned {result['row_count']} "
                        f"{result['dimension']} group(s) for {result['metric']}."
                    ),
                    tool_events=events,
                    data={
                        "type": "safe_sql_analysis",
                        "query_spec": payload,
                        **result,
                    },
                )
            }

        if plan.intent == "compare_analysis":
            if len(plan.analysis_steps) < 2:
                return {
                    "result": ExecutionResult(
                        message=(
                            "A comparison needs 2 to 4 explicit read-only slices, "
                            "such as two projects or two date ranges."
                        )
                    )
                }
            if len({step.label.casefold() for step in plan.analysis_steps}) != len(
                plan.analysis_steps
            ):
                return {
                    "result": ExecutionResult(
                        message="Every comparison slice needs a distinct label."
                    )
                }
            projects = await core.list_projects(actor_id)
            events = [tool_event("list_projects", {}, projects)]
            resolved_steps = []
            for step in plan.analysis_steps:
                if (step.start_date is None) != (step.end_date is None):
                    return {
                        "result": ExecutionResult(
                            message=f"Comparison slice {step.label} needs both dates."
                        )
                    }
                if (
                    step.start_date is not None
                    and step.end_date is not None
                    and step.start_date > step.end_date
                ):
                    return {
                        "result": ExecutionResult(
                            message=f"Comparison slice {step.label} has an invalid range."
                        )
                    }
                project = None
                if step.project_id is not None or step.project_name is not None:
                    project = resolve_project(
                        projects,
                        AgentPlan(
                            intent="time_entries",
                            project_id=step.project_id,
                            project_name=step.project_name,
                        ),
                    )
                    if project is None:
                        return {
                            "result": ExecutionResult(
                                message=(
                                    f"Comparison slice {step.label} references a "
                                    "project outside your authorized scope."
                                ),
                                tool_events=events,
                            )
                        }
                resolved_steps.append((step, project))

            # Validate every slice before executing the first data query. This
            # prevents a partially executed plan when a later slice is invalid.
            rows = []
            for step, project in resolved_steps:
                filters = {
                    "project_id": project["id"] if project else None,
                    "status": step.entry_status,
                    "start_date": step.start_date,
                    "end_date": step.end_date,
                }
                entries = await core.list_time_entries(actor_id, **filters)
                events.append(
                    tool_event(
                        "list_time_entries",
                        {
                            key: value.isoformat()
                            if hasattr(value, "isoformat")
                            else value
                            for key, value in filters.items()
                            if value is not None
                        },
                        entries,
                    )
                )
                total = sum(
                    (Decimal(str(entry["hours"])) for entry in entries),
                    Decimal("0"),
                )
                rows.append(
                    {
                        "label": step.label,
                        "project_name": project["name"] if project else None,
                        "start_date": step.start_date,
                        "end_date": step.end_date,
                        "status": step.entry_status,
                        "entry_count": len(entries),
                        "hours": str(total),
                    }
                )
            baseline = Decimal(rows[0]["hours"])
            for row in rows:
                row["delta_from_first"] = str(Decimal(row["hours"]) - baseline)
            return {
                "result": ExecutionResult(
                    message=(
                        f"I executed {len(rows)} authorized comparison slices. "
                        "The results and deltas are shown below."
                    ),
                    tool_events=events,
                    data={
                        "type": "comparison",
                        "baseline": rows[0]["label"],
                        "rows": rows,
                    },
                )
            }

        if plan.intent == "decide_time_entries":
            if not plan.time_entry_ids or plan.approval_decision is None:
                return {"result": ExecutionResult(message="Provide 1–20 exact entry IDs and an approve or reject decision.")}
            actor = await core.get_me(actor_id)
            events = [tool_event("get_current_actor", {}, actor)]
            if actor["role"] == "employee":
                return {"result": ExecutionResult(message="Employees cannot approve or reject time entries, so no dry-run was created.", tool_events=events)}
            payload = {
                "entry_ids": plan.time_entry_ids,
                "decision": plan.approval_decision,
                "comment": plan.approval_comment,
            }
            preview = await core.dry_run_approval_batch(actor_id, payload)
            events.append(tool_event("dry_run_time_entry_approval_batch", payload, preview))
            card = ConfirmationCard(
                action=preview["action"], preview=preview["preview"],
                confirmation_token=preview["confirmation_token"], expires_at=preview["expires_at"],
                confirm_path=f"/actions/{preview['confirmation_token']}/confirm",
            )
            return {"result": ExecutionResult(
                message=f"I prepared an atomic {len(plan.time_entry_ids)}-entry approval dry-run. Nothing changed yet.",
                tool_events=events, data=preview["preview"], confirmation=card,
            )}

        if plan.intent == "decide_time_entry":
            if plan.time_entry_id is None or plan.approval_decision is None:
                return {
                    "result": ExecutionResult(
                        message=(
                            "Provide an exact time-entry ID and explicitly say "
                            "approve or reject before I create an approval dry-run."
                        )
                    )
                }
            actor = await core.get_me(actor_id)
            events = [tool_event("get_current_actor", {}, actor)]
            if actor["role"] == "employee":
                return {
                    "result": ExecutionResult(
                        message=(
                            "Employees cannot approve or reject time entries, "
                            "so no dry-run was created."
                        ),
                        tool_events=events,
                    )
                }
            payload = {
                "decision": plan.approval_decision,
                "comment": plan.approval_comment,
            }
            preview = await core.dry_run_approval(
                actor_id, plan.time_entry_id, payload
            )
            events.append(
                tool_event(
                    "dry_run_time_entry_approval",
                    {"time_entry_id": plan.time_entry_id, **payload},
                    preview,
                )
            )
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
                        f"I prepared a dry-run to {plan.approval_decision} "
                        f"time entry {plan.time_entry_id}. Its status has not "
                        "changed; review the card before explicit confirmation."
                    ),
                    tool_events=events,
                    data=preview["preview"],
                    confirmation=card,
                )
            }

        if plan.intent == "suggest_time_entries":
            suggestions = await core.get_time_entry_suggestions(
                actor_id, plan.work_date
            )
            return {
                "result": ExecutionResult(
                    message=(
                        f"I found {len(suggestions)} non-authoritative suggestion"
                        f"{'s' if len(suggestions) != 1 else ''} based on your "
                        "own recent entries. Review and edit every field before "
                        "requesting a draft."
                    ),
                    tool_events=[
                        tool_event(
                            "get_time_entry_suggestions",
                            {
                                "target_date": (
                                    plan.work_date.isoformat()
                                    if plan.work_date
                                    else None
                                )
                            },
                            suggestions,
                        )
                    ],
                    data={
                        "type": "time_entry_suggestions",
                        "suggestions": suggestions,
                    },
                )
            }

        if plan.intent == "draft_time_entries_batch":
            if not plan.batch_entries:
                return {
                    "result": ExecutionResult(
                        message=(
                            "Provide 1 to 10 explicit batch items. Every item "
                            "needs project, work_date, hours, and description."
                        )
                    )
                }
            missing_items = []
            for index, item in enumerate(plan.batch_entries, start=1):
                missing = [
                    name
                    for name, value in (
                        ("project", item.project_id or item.project_name),
                        ("work_date", item.work_date),
                        ("hours", item.hours),
                        ("description", item.description),
                    )
                    if value is None
                ]
                if missing:
                    missing_items.append(f"item {index}: {', '.join(missing)}")
            if missing_items:
                return {
                    "result": ExecutionResult(
                        message=(
                            "I need exact values before creating a batch dry-run: "
                            + "; ".join(missing_items)
                            + "."
                        )
                    )
                }

            projects = await core.list_projects(actor_id)
            events = [tool_event("list_projects", {}, projects)]
            payload_entries = []
            for index, item in enumerate(plan.batch_entries, start=1):
                project = next(
                    (
                        project
                        for project in projects
                        if (
                            item.project_id is not None
                            and project["id"] == item.project_id
                        )
                        or (
                            item.project_name is not None
                            and item.project_name.casefold()
                            in {
                                project["name"].casefold(),
                                project["code"].casefold(),
                            }
                        )
                    ),
                    None,
                )
                if project is None:
                    return {
                        "result": ExecutionResult(
                            message=(
                                f"Batch item {index} references a project outside "
                                "your authorized scope."
                            ),
                            tool_events=events,
                        )
                    }
                payload_entries.append(
                    {
                        "project_id": project["id"],
                        "work_date": item.work_date.isoformat(),
                        "hours": str(item.hours),
                        "description": item.description,
                    }
                )
            payload = {"entries": payload_entries}
            preview = await core.dry_run_time_entry_batch(actor_id, payload)
            events.append(
                tool_event("dry_run_time_entry_batch", payload, preview)
            )
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
                        f"I prepared a {len(payload_entries)}-item batch dry-run. "
                        "Review every item; nothing has been written yet."
                    ),
                    tool_events=events,
                    data=preview["preview"],
                    confirmation=card,
                )
            }

        if plan.intent == "manage_time_entry":
            if plan.time_entry_id is None or plan.lifecycle_action is None:
                return {"result": ExecutionResult(message="Specify an exact time-entry ID and lifecycle action.")}
            payload = None
            events = []
            if plan.lifecycle_action == "update":
                payload = {}
                if plan.project_id or plan.project_name:
                    projects = await core.list_projects(actor_id)
                    events.append(tool_event("list_projects", {}, projects))
                    project = resolve_project(projects, plan)
                    if project is None:
                        return {"result": ExecutionResult(message="That project is not available in your authorized scope.", tool_events=events)}
                    payload["project_id"] = project["id"]
                if plan.work_date is not None:
                    payload["work_date"] = plan.work_date.isoformat()
                if plan.hours is not None:
                    payload["hours"] = str(plan.hours)
                if plan.description is not None:
                    payload["description"] = plan.description
                if not payload:
                    return {"result": ExecutionResult(message="Specify at least one exact field to update: project, date, hours, or description.")}
            preview = await core.dry_run_time_entry_lifecycle(
                actor_id, plan.time_entry_id, plan.lifecycle_action, payload
            )
            events.append(tool_event(f"dry_run_time_entry_{plan.lifecycle_action}", payload or {"entry_id": plan.time_entry_id}, preview))
            card = ConfirmationCard(
                action=preview["action"],
                preview=preview["preview"],
                confirmation_token=preview["confirmation_token"],
                expires_at=preview["expires_at"],
                confirm_path=f"/actions/{preview['confirmation_token']}/confirm",
            )
            return {"result": ExecutionResult(
                message=f"I prepared a {plan.lifecycle_action} dry-run for time entry {plan.time_entry_id}. Nothing changed yet.",
                tool_events=events,
                data=preview["preview"],
                confirmation=card,
            )}

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
        if (
            state["plan"].intent
            in {
                "draft_time_entry",
                "draft_time_entries_batch",
                "decide_time_entry",
                "decide_time_entries",
                "manage_time_entry",
            }
            and result.confirmation is None
        ):
            # A model must never rewrite a missing-field or rejected write as
            # a successful draft. Only a real confirmation card permits LLM
            # wording of the dry-run result.
            message = result.message
        else:
            message = await response_composer.compose(
                state["message"],
                state["plan"],
                result,
                state.get("planner_context"),
                state["actor_id"],
            )
        return {
            "response": ChatResponse(
                message=message,
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
