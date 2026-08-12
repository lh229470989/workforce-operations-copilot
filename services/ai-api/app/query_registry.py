from collections import defaultdict
from decimal import Decimal
from typing import Any
from uuid import uuid4

from .core_client import CoreAPIClient
from .schemas import (
    AgentPlan,
    ChartData,
    ExecutionResult,
    ToolEvent,
)

READ_INTENTS = frozenset(
    {
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
        "export_report",
        "pending_team",
    }
)


def tool_event(
    name: str, tool_input: dict[str, Any], output: Any
) -> ToolEvent:
    return ToolEvent(
        id=str(uuid4()),
        name=name,
        input=tool_input,
        output=output,
    )


def resolve_project(
    projects: list[dict[str, Any]], plan: AgentPlan
) -> dict[str, Any] | None:
    if plan.project_id is not None:
        return next(
            (project for project in projects if project["id"] == plan.project_id),
            None,
        )
    if plan.project_name:
        target = plan.project_name.casefold()
        return next(
            (
                project
                for project in projects
                if project["name"].casefold() == target
                or project["code"].casefold() == target
            ),
            None,
        )
    return None


class ReadQueryRegistry:
    """Executes only role-scoped read capabilities exposed by Core API."""

    def __init__(self, core: CoreAPIClient) -> None:
        self.core = core

    def handles(self, intent: str) -> bool:
        return intent in READ_INTENTS

    async def execute(self, plan: AgentPlan, actor_id: int) -> ExecutionResult:
        handler = getattr(self, f"_handle_{plan.intent}", None)
        if handler is None or not self.handles(plan.intent):
            return ExecutionResult(message="No registered read query was selected.")
        return await handler(plan, actor_id)

    async def _handle_current_user(
        self, _: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        actor = await self.core.get_me(actor_id)
        article = "an" if actor["role"][0].lower() in "aeiou" else "a"
        return ExecutionResult(
            message=(
                f"You are {actor['name']}, {article} {actor['role']} with the title "
                f"{actor['title']}."
            ),
            tool_events=[tool_event("get_current_actor", {}, actor)],
            data=actor,
        )

    async def _handle_list_departments(
        self, _: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        departments = await self.core.list_departments(actor_id)
        names = ", ".join(item["name"] for item in departments) or "none"
        return ExecutionResult(
            message=f"Your visible departments are: {names}.",
            tool_events=[tool_event("list_departments", {}, departments)],
            data=departments,
        )

    async def _handle_weekly_report(
        self, plan: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        report = await self.core.get_weekly_report(actor_id, plan.start_date)
        data = {"type": "weekly_report", **report}
        return ExecutionResult(
            message=(
                f"Weekly report for {report['week_start']} through "
                f"{report['week_end']}: {report['total_hours']} hours across "
                f"{report['entry_count']} entries. A role-scoped CSV is ready."
            ),
            tool_events=[
                tool_event(
                    "get_weekly_report",
                    {"week_start": report["week_start"]},
                    report,
                )
            ],
            data=data,
        )

    async def _handle_export_report(
        self, plan: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        """Prepare a role-scoped download descriptor for the web client."""

        entries, project, events = await self._filtered_entries(plan, actor_id)
        if entries is None:
            return ExecutionResult(
                message="That project is not available in your authorized scope.",
                tool_events=events,
            )
        filters = {
            "project_id": project["id"] if project else None,
            "status": plan.entry_status,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
        }
        return ExecutionResult(
            message=(
                f"Your role-scoped CSV export is ready with {len(entries)} "
                "matching time entries."
            ),
            tool_events=events,
            data={
                "type": "report_export",
                "format": "csv",
                "row_count": len(entries),
                "filters": {key: value for key, value in filters.items() if value is not None},
            },
        )

    async def _handle_list_employees(
        self, _: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        employees = await self.core.list_employees(actor_id)
        names = ", ".join(item["name"] for item in employees) or "none"
        noun = "employee is" if len(employees) == 1 else "employees are"
        return ExecutionResult(
            message=(
                f"{len(employees)} {noun} visible in your role scope: {names}."
            ),
            tool_events=[tool_event("list_employees", {}, employees)],
            data=employees,
        )

    async def _handle_list_projects(
        self, _: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        projects = await self.core.list_projects(actor_id)
        names = ", ".join(project["name"] for project in projects) or "none"
        return ExecutionResult(
            message=f"Your visible projects are: {names}.",
            tool_events=[tool_event("list_projects", {}, projects)],
            data=projects,
        )

    async def _project_context(
        self, plan: AgentPlan, actor_id: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[ToolEvent]]:
        projects = await self.core.list_projects(actor_id)
        events = [tool_event("list_projects", {}, projects)]
        project = resolve_project(projects, plan)
        return projects, project, events

    async def _handle_project_members(
        self, plan: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        _, project, events = await self._project_context(plan, actor_id)
        if project is None:
            return ExecutionResult(
                message=(
                    "Specify one visible project to list its members."
                    if not (plan.project_id or plan.project_name)
                    else "That project is not available in your authorized scope."
                ),
                tool_events=events,
            )
        members = await self.core.list_project_members(actor_id, project["id"])
        employees = await self.core.list_employees(actor_id)
        employee_names = {item["id"]: item["name"] for item in employees}
        enriched = [
            {
                **member,
                "employee_name": employee_names.get(
                    member["employee_id"], "Outside visible employee scope"
                ),
            }
            for member in members
        ]
        events.extend(
            [
                tool_event(
                    "list_project_members",
                    {"project_id": project["id"]},
                    members,
                ),
                tool_event("list_employees", {}, employees),
            ]
        )
        noun = "member is" if len(enriched) == 1 else "members are"
        return ExecutionResult(
            message=(
                f"{len(enriched)} {noun} visible on {project['name']} "
                "within your role scope."
            ),
            tool_events=events,
            data=enriched,
        )

    async def _filtered_entries(
        self, plan: AgentPlan, actor_id: int
    ) -> tuple[
        list[dict[str, Any]] | None,
        dict[str, Any] | None,
        list[ToolEvent],
    ]:
        _, project, events = await self._project_context(plan, actor_id)
        if (plan.project_id or plan.project_name) and project is None:
            return None, None, events
        filters = {
            "project_id": project["id"] if project else None,
            "status": plan.entry_status,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
        }
        entries = await self.core.list_time_entries(actor_id, **filters)
        if plan.limit is not None:
            entries = entries[: plan.limit]
        event_filters = {
            **filters,
            "limit": plan.limit,
        }
        events.append(tool_event("list_time_entries", event_filters, entries))
        return entries, project, events

    async def _handle_time_entries(
        self, plan: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        result = await self._filtered_entries(plan, actor_id)
        entries, project, events = result
        if entries is None:
            return ExecutionResult(
                message="That project is not available in your authorized scope.",
                tool_events=events,
            )
        qualifiers = []
        if plan.entry_status:
            qualifiers.append(plan.entry_status)
        if project:
            qualifiers.append(project["name"])
        label = f" {' '.join(qualifiers)}" if qualifiers else ""
        noun = "time entry" if len(entries) == 1 else "time entries"
        project_names = {
            item["id"]: item["name"] for item in events[0].output
        }
        # The web renders these authorized rows directly. Supplying the
        # project label here avoids asking the model or browser to infer it.
        enriched_entries = [
            {
                **entry,
                "project_name": project_names.get(
                    entry["project_id"], "Unavailable project"
                ),
            }
            for entry in entries
        ]
        return ExecutionResult(
            message=f"I found {len(entries)}{label} {noun} in your role scope.",
            tool_events=events,
            data=enriched_entries,
        )

    async def _handle_hours_by_project(
        self, plan: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        result = await self._filtered_entries(plan, actor_id)
        entries, project, events = result
        if entries is None:
            return ExecutionResult(
                message="That project is not available in your authorized scope.",
                tool_events=events,
            )
        total = sum(
            (Decimal(str(entry["hours"])) for entry in entries), Decimal("0")
        )
        project_label = project["name"] if project else "all visible projects"
        date_label = ""
        if plan.start_date:
            date_label = f" from {plan.start_date}"
            if plan.end_date and plan.end_date != plan.start_date:
                date_label += f" through {plan.end_date}"
        status_label = f" ({plan.entry_status})" if plan.entry_status else ""
        return ExecutionResult(
            message=(
                f"You logged {total:.2f} hours on {project_label}"
                f"{date_label}{status_label}."
            ),
            tool_events=events,
            data={"hours": f"{total:.2f}", "entries": entries},
        )

    async def _handle_summary(
        self, _: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        summary = await self.core.get_summary(actor_id)
        return ExecutionResult(
            message=(
                f"Your role-scoped total is {Decimal(str(summary['total_hours'])):.2f} "
                "hours, including "
                f"{Decimal(str(summary['approved_hours'])):.2f} approved and "
                f"{Decimal(str(summary['submitted_hours'])):.2f} submitted hours."
            ),
            tool_events=[tool_event("get_time_summary", {}, summary)],
            data=summary,
        )

    async def _handle_monthly_chart(
        self, plan: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        result = await self._filtered_entries(plan, actor_id)
        entries, _, events = result
        if entries is None:
            return ExecutionResult(
                message="That project is not available in your authorized scope.",
                tool_events=events,
            )
        projects = events[0].output
        project_names = {
            project["id"]: project["name"] for project in projects
        }
        totals: defaultdict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for entry in entries:
            month = entry["work_date"][:7]
            name = project_names.get(entry["project_id"], "Unknown")
            totals[(month, name)] += Decimal(str(entry["hours"]))
        rows = [
            {"month": month, "project": project, "hours": str(hours)}
            for (month, project), hours in sorted(totals.items())
        ]
        chart = ChartData(
            type="bar",
            title="Monthly hours by project",
            x_key="month",
            series_key="project",
            value_key="hours",
            rows=rows,
        )
        return ExecutionResult(
            message="Here are your role-scoped monthly hours by project.",
            tool_events=events,
            data=chart.model_dump(mode="json"),
        )

    async def _handle_pending_team(
        self, _: AgentPlan, actor_id: int
    ) -> ExecutionResult:
        actor = await self.core.get_me(actor_id)
        entries = await self.core.list_time_entries(
            actor_id, status="submitted"
        )
        events = [
            tool_event("get_current_actor", {}, actor),
            tool_event(
                "list_time_entries",
                {"status": "submitted"},
                entries,
            ),
        ]
        if actor["role"] == "employee":
            message = (
                "Employees cannot approve time entries. "
                f"You have {len(entries)} submitted entries in your own scope."
            )
        else:
            message = (
                f"You can decide eligible direct-report entries, and {len(entries)} "
                "submitted entries are visible. This request only inspected the "
                "queue; provide an exact entry ID and approve/reject decision to "
                "create a dry-run proposal."
            )
        return ExecutionResult(
            message=message,
            tool_events=events,
            data=entries,
        )
