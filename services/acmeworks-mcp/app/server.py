"""AcmeWorks MCP server exposing scoped reads and preview-only write tools."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .core_client import CoreAPIClient


READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
PREVIEW_ONLY = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


def _compact(payload: Any) -> str:
    """Create readable fallback text for MCP clients without structured output."""

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _dry_run_result(result: dict[str, Any]) -> CallToolResult:
    """Keep the confirmation secret out of model-visible tool content.

    MCP clients may use ``_meta.confirmation`` to build a trusted confirmation
    UI. The server intentionally exposes no confirmation tool, so an LLM cannot
    turn its own preview into a write.
    """

    visible = {key: value for key, value in result.items() if key != "confirmation_token"}
    visible["next_step"] = "Review and confirm this action in the trusted AcmeWorks web UI."
    return CallToolResult(
        content=[TextContent(type="text", text=_compact(visible))],
        structuredContent=visible,
        _meta={
            "confirmation": {
                "token": result["confirmation_token"],
                "expires_at": result["expires_at"],
                "confirm_via": "trusted-ui-only",
            }
        },
    )


def create_server(client: CoreAPIClient | None = None) -> MCPServer:
    """Build a server with an injectable Core client for protocol-level tests."""

    core = client or CoreAPIClient()
    server = MCPServer(
        name="acmeworks-workforce-operations",
        title="AcmeWorks Workforce Operations",
        description="Scoped access to fully fictional AcmeWorks workforce data.",
        instructions=(
            "Always ask for the user's demo actor ID. Respect the returned scope. "
            "Write tools only prepare a dry-run; never claim that a preview was saved."
        ),
        version="0.1.0",
    )

    @server.tool(annotations=READ_ONLY)
    async def get_current_user(actor_id: int) -> dict[str, Any]:
        """Return the selected fictional actor and their server-enforced role."""

        return await core.get("/me", actor_id)

    @server.tool(annotations=READ_ONLY)
    async def list_departments(actor_id: int) -> list[dict[str, Any]]:
        """List departments visible to the selected actor."""

        return await core.get("/departments", actor_id)

    @server.tool(annotations=READ_ONLY)
    async def list_employees(actor_id: int) -> list[dict[str, Any]]:
        """List employees in the selected actor's authorized scope."""

        return await core.get("/employees", actor_id)

    @server.tool(annotations=READ_ONLY)
    async def list_projects(actor_id: int) -> list[dict[str, Any]]:
        """List projects visible to the selected actor."""

        return await core.get("/projects", actor_id)

    @server.tool(annotations=READ_ONLY)
    async def list_project_members(actor_id: int, project_id: int) -> list[dict[str, Any]]:
        """List visible members of an exact project ID."""

        return await core.get(f"/projects/{project_id}/members", actor_id)

    @server.tool(annotations=READ_ONLY)
    async def list_time_entries(
        actor_id: int,
        employee_id: int | None = None,
        project_id: int | None = None,
        status: Literal["draft", "submitted", "approved", "rejected"] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """List scoped time entries using bounded business filters."""

        return await core.get(
            "/time-entries",
            actor_id,
            employee_id=employee_id,
            project_id=project_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )

    @server.tool(annotations=READ_ONLY)
    async def get_time_summary(actor_id: int) -> dict[str, Any]:
        """Summarize visible hours by workflow status."""

        return await core.get("/stats/summary", actor_id)

    @server.tool(annotations=READ_ONLY)
    async def get_pending_approvals(actor_id: int) -> list[dict[str, Any]]:
        """Return submitted entries that this actor can see and potentially review."""

        return await core.get("/time-entries", actor_id, status="submitted")

    @server.tool(annotations=READ_ONLY)
    async def query_safe_analytics(
        actor_id: int,
        dimension: Literal["project", "status", "employee", "work_date", "month"],
        metric: Literal["hours", "entry_count"] = "hours",
        start_date: date | None = None,
        end_date: date | None = None,
        status: Literal["draft", "submitted", "approved", "rejected"] | None = None,
        project_id: int | None = None,
        employee_id: int | None = None,
        order: Literal["asc", "desc"] = "desc",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Run a declarative, read-only aggregation; arbitrary SQL is never accepted."""

        return await core.post(
            "/analytics/query",
            actor_id,
            {
                "dimension": dimension,
                "metric": metric,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "status": status,
                "project_id": project_id,
                "employee_id": employee_id,
                "order": order,
                "limit": limit,
            },
        )

    @server.tool(annotations=PREVIEW_ONLY)
    async def create_time_entry_dry_run(
        actor_id: int,
        project_id: int,
        work_date: date,
        hours: Decimal,
        description: str,
        employee_id: int | None = None,
    ) -> CallToolResult:
        """Validate and preview a time entry without saving it."""

        result = await core.post(
            "/time-entries/dry-run",
            actor_id,
            {
                "employee_id": employee_id,
                "project_id": project_id,
                "work_date": work_date.isoformat(),
                "hours": str(hours),
                "description": description,
            },
        )
        return _dry_run_result(result)

    @server.tool(annotations=PREVIEW_ONLY)
    async def create_approval_dry_run(
        actor_id: int,
        entry_id: int,
        decision: Literal["approved", "rejected"],
        comment: str | None = None,
    ) -> CallToolResult:
        """Validate and preview one approval decision without applying it."""

        result = await core.post(
            f"/time-entries/{entry_id}/approval/dry-run",
            actor_id,
            {"decision": decision, "comment": comment},
        )
        return _dry_run_result(result)

    @server.resource(
        "acmeworks://capabilities",
        name="AcmeWorks capability guide",
        mime_type="text/markdown",
    )
    def capability_guide() -> str:
        """Describe supported operations and immutable safety constraints."""

        return (
            "# AcmeWorks MCP\n\n"
            "All people and business records are fictional. Reads are scoped by actor_id. "
            "Write tools create previews only; confirmation belongs to a trusted UI. "
            "The server never accepts arbitrary SQL."
        )

    @server.resource(
        "acmeworks://actors/{actor_id}/scope",
        name="Actor scope",
        mime_type="application/json",
    )
    async def actor_scope(actor_id: int) -> str:
        """Return the authoritative persona plus employees and projects it can see."""

        payload = {
            "actor": await core.get("/me", actor_id),
            "employees": await core.get("/employees", actor_id),
            "projects": await core.get("/projects", actor_id),
        }
        return _compact(payload)

    @server.prompt()
    def weekly_report(actor_id: int, week_start: str = "current week") -> str:
        """Plan a concise, evidence-backed weekly time report."""

        return (
            f"For demo actor {actor_id}, prepare a report for {week_start}. "
            "Use scoped AcmeWorks tools, separate recorded facts from interpretation, "
            "and identify missing or unsubmitted time."
        )

    @server.prompt()
    def review_pending_time(actor_id: int) -> str:
        """Review pending approvals without applying decisions."""

        return (
            f"Review submitted entries visible to demo actor {actor_id}. Highlight anomalies, "
            "but do not approve or reject anything unless the user asks for a dry-run preview."
        )

    @server.prompt()
    def prepare_time_entry(actor_id: int, work_description: str) -> str:
        """Gather exact fields before preparing a time-entry dry-run."""

        return (
            f"Help demo actor {actor_id} prepare this work entry: {work_description}. "
            "Resolve an exact project, work date, hours, and description, then call only the dry-run tool."
        )

    @server.prompt()
    def compare_project_hours(actor_id: int, period: str) -> str:
        """Compare project hours with a bounded analytics query."""

        return (
            f"For demo actor {actor_id}, compare project hours for {period}. "
            "Use query_safe_analytics and state the exact filters used."
        )

    return server


mcp = create_server()
