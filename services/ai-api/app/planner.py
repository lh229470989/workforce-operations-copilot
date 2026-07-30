import json
import re
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Protocol

from openai import AsyncOpenAI

from .conversation_context import (
    infer_local_conversation_relation,
    resolve_plan_context,
)
from .schemas import AgentPlan, PlannerContext

PROJECT_NAMES = ("Apollo", "Beacon", "Cedar")

PLANNER_INSTRUCTIONS = """
You plan one safe operation for a fictional workforce assistant.

Available intents:
- current_user: show the current fictional actor profile.
- list_departments: list role-scoped departments.
- list_employees: list role-scoped employees or team members.
- list_projects: list visible projects.
- project_members: list visible members for one project.
- time_entries: list role-scoped time entries, optionally by status/project/date.
- hours_by_project: total role-scoped hours, optionally by project/date range.
- summary: summarize hours by workflow status.
- monthly_chart: monthly hours grouped by project.
- pending_team: inspect pending submitted time and explain approval eligibility.
- policy_question: answer from the supplied AcmeWorks policy knowledge base.
- draft_time_entry: create a dry-run preview only.
- capabilities: explain supported actions.
- unknown: the request cannot be mapped safely.

Authorization and write boundaries:
- The server supplies the actor identity. Never infer or change it.
- Read tools are role-scoped by the downstream server.
- The only write-capable tool creates a dry-run preview. Never confirm it.
- There is no approval write tool.
- A draft requires project, work_date, hours, and description. Leave missing
  fields null; do not invent them.
- Resolve unambiguous relative read ranges such as today, yesterday, this/last
  week, this/last month, or the last N days from the supplied current date.
- The limit field applies only to time-entry lists, not hour totals.
- Never invent a missing date for a time-entry draft.
- Decide whether the request is independent, refines the previous read, switches
  the subject of the previous read, or references authoritative actor context.
- For a follow-up, set conversation_relation and list only the omitted read
  filters that should be reused in inherit_fields.
- Use project_reference="recent" for phrases such as "my recent project"; do
  not guess a project name from conversation prose.
- Leave field_resolutions empty. The server records field provenance after it
  applies inheritance and actor-context policy.
Return exactly one AgentPlan.
""".strip()


def _extract_project_name(text: str) -> str | None:
    lowered = text.lower()
    known = next(
        (name for name in PROJECT_NAMES if name.lower() in lowered), None
    )
    if known:
        return known
    patterns = (
        r"\bon\s+([A-Za-z][\w-]*)",
        r"\b([A-Za-z][\w-]*)\s+project\b",
        r"\bproject\s+([A-Za-z][\w-]*)",
        r"\b([A-Za-z][\w-]*)\s*项目",
    )
    ignored = {
        "a",
        "all",
        "as",
        "by",
        "latest",
        "my",
        "recent",
        "the",
        "this",
        "visible",
    }
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and match.group(1).lower() not in ignored:
            return match.group(1)
    return None


def _read_date_range(
    text: str, lowered: str, today: date, dates: list[date]
) -> tuple[date | None, date | None]:
    if dates:
        return dates[0], dates[1] if len(dates) > 1 else dates[0]
    if "today" in lowered or "今天" in text:
        return today, today
    if "yesterday" in lowered or "昨天" in text:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if "last week" in lowered or "上周" in text:
        this_week = today - timedelta(days=today.weekday())
        return this_week - timedelta(days=7), this_week - timedelta(days=1)
    if "this week" in lowered or "本周" in text or "这周" in text:
        return today - timedelta(days=today.weekday()), today
    if "last month" in lowered or "上个月" in text or "上月" in text:
        current_month = today.replace(day=1)
        previous_end = current_month - timedelta(days=1)
        return previous_end.replace(day=1), previous_end
    if "this month" in lowered or "本月" in text or "这个月" in text:
        return today.replace(day=1), today
    recent_match = re.search(
        r"(?:last|past|recent)\s+(\d{1,2})\s+days?", lowered
    ) or re.search(r"最近\s*(\d{1,2})\s*天", text)
    if recent_match:
        days = max(1, min(int(recent_match.group(1)), 90))
        return today - timedelta(days=days - 1), today
    return None, None


def _entry_status(text: str, lowered: str) -> str | None:
    statuses = {
        "submitted": ("submitted", "待审批", "已提交"),
        "approved": ("approved", "已审批", "已批准"),
        "draft": ("draft entries", "draft records", "草稿"),
        "rejected": ("rejected", "已拒绝", "驳回"),
    }
    return next(
        (
            status
            for status, words in statuses.items()
            if any(word in lowered or word in text for word in words)
        ),
        None,
    )


def _entry_limit(text: str, lowered: str) -> int | None:
    match = re.search(
        r"(?:last|latest|recent)\s+(\d{1,2})"
        r"(?:\s+(?:submitted|approved|draft|rejected))?\s+"
        r"(?:time\s+entries|entries|records)", lowered
    ) or re.search(r"最近\s*(\d{1,2})\s*条", text)
    return min(int(match.group(1)), 50) if match else None


class Planner(Protocol):
    async def plan(
        self,
        message: str,
        today: date,
        actor_id: int,
        context: PlannerContext | None = None,
    ) -> AgentPlan: ...

    async def close(self) -> None: ...


class LocalPlanner:
    async def close(self) -> None:
        return None

    async def plan(
        self,
        message: str,
        today: date,
        actor_id: int,
        context: PlannerContext | None = None,
    ) -> AgentPlan:
        plan = await self._plan_without_context(message, today, actor_id)
        lowered = message.casefold()
        if any(
            phrase in lowered
            for phrase in (
                "recent project",
                "latest project",
                "最近项目",
                "最近填报项目",
            )
        ):
            plan = plan.model_copy(
                update={
                    "conversation_relation": "use_actor_context",
                    "project_reference": "recent",
                    "project_name": None,
                }
            )
        plan = infer_local_conversation_relation(plan, context)
        return resolve_plan_context(plan, context)

    async def _plan_without_context(
        self, message: str, today: date, actor_id: int
    ) -> AgentPlan:
        text = message.strip()
        lowered = text.lower()
        project_name = _extract_project_name(text)
        dates = [
            date.fromisoformat(value)
            for value in re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        ]
        start_date, end_date = _read_date_range(
            text, lowered, today, dates
        )
        entry_status = _entry_status(text, lowered)

        if any(
            word in lowered
            for word in (
                "draft",
                "草稿",
                "记录工时",
                "补工时",
                "填报",
                "登记工时",
            )
        ):
            hours_match = re.search(
                r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|小时)", lowered
            )
            description_match = re.search(r"[:：]\s*(.+)$", text)
            return AgentPlan(
                intent="draft_time_entry",
                project_name=project_name,
                work_date=dates[0] if dates else None,
                hours=Decimal(hours_match.group(1)) if hours_match else None,
                description=(
                    description_match.group(1).strip()
                    if description_match
                    else None
                ),
            )

        if (
            ("monthly" in lowered or "月" in text)
            and any(word in lowered for word in ("chart", "hours", "工时", "图"))
        ):
            return AgentPlan(
                intent="monthly_chart",
                project_name=project_name,
                start_date=start_date,
                end_date=end_date,
                entry_status=entry_status,
            )

        if any(
            phrase in lowered
            for phrase in (
                "policy",
                "submission deadline",
                "collaboration hours",
                "overtime rule",
                "data retention",
                "demo data",
            )
        ) or any(
            phrase in text
            for phrase in (
                "政策",
                "提交截止",
                "协作时间",
                "加班规定",
                "数据保留",
                "演示数据",
            )
        ):
            return AgentPlan(intent="policy_question")

        if any(word in lowered for word in ("approve", "approval", "审批", "批准")):
            return AgentPlan(intent="pending_team")

        if any(
            phrase in lowered
            for phrase in ("who am i", "my profile", "current user")
        ) or any(phrase in text for phrase in ("我是谁", "我的身份", "我的信息")):
            return AgentPlan(intent="current_user")

        if any(
            word in lowered for word in ("department", "departments")
        ) or "部门" in text:
            return AgentPlan(intent="list_departments")

        if project_name and (
            any(
                phrase in lowered
                for phrase in ("project members", "project team", "who is on")
            )
            or "项目成员" in text
            or ("成员" in text and "项目" in text)
        ):
            return AgentPlan(
                intent="project_members", project_name=project_name
            )

        if any(
            phrase in lowered
            for phrase in (
                "employees",
                "team members",
                "direct reports",
                "my team",
            )
        ) or any(phrase in text for phrase in ("员工", "团队成员", "下属")):
            return AgentPlan(intent="list_employees")

        if any(word in lowered for word in ("project", "项目")) and any(
            word in lowered for word in ("list", "which", "哪些", "列出")
        ):
            return AgentPlan(intent="list_projects")

        if any(
            phrase in lowered
            for phrase in (
                "time summary",
                "hours summary",
                "status summary",
                "status breakdown",
                "overview of my hours",
            )
        ) or any(phrase in text for phrase in ("工时概览", "工时汇总", "状态统计")):
            return AgentPlan(intent="summary")

        if any(
            phrase in lowered
            for phrase in (
                "time entries",
                "time entry list",
                "work records",
                "timesheet records",
                "recent entries",
            )
        ) or any(
            phrase in text
            for phrase in ("工时记录", "填报记录", "工时明细", "最近的工时")
        ):
            return AgentPlan(
                intent="time_entries",
                project_name=project_name,
                start_date=start_date,
                end_date=end_date,
                entry_status=entry_status,
                limit=_entry_limit(text, lowered),
            )

        if any(
            phrase in lowered
            for phrase in ("how many hours", "hours did", "logged", "工时", "小时")
        ):
            return AgentPlan(
                intent="hours_by_project",
                project_name=project_name,
                start_date=start_date,
                end_date=end_date,
                entry_status=entry_status,
            )

        if any(word in lowered for word in ("can you", "capabilities", "能做什么")):
            return AgentPlan(intent="capabilities")
        return AgentPlan(
            intent="unknown",
            project_name=project_name,
            entry_status=entry_status,
            start_date=start_date,
            end_date=end_date,
        )


class OpenAIPlanner:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def close(self) -> None:
        await self._client.close()

    async def plan(
        self,
        message: str,
        today: date,
        actor_id: int,
        context: PlannerContext | None = None,
    ) -> AgentPlan:
        safety_identifier = sha256(
            f"acmeworks-demo:{actor_id}".encode()
        ).hexdigest()[:32]
        context_text = ""
        if context is not None:
            context_text = (
                "\nAuthoritative fictional actor and short-session context:\n"
                + json.dumps(context.model_dump(mode="json"), ensure_ascii=False)
            )
        response = await self._client.responses.parse(
            model=self._model,
            instructions=PLANNER_INSTRUCTIONS,
            input=(
                f"Today is {today.isoformat()}.\nUser request: {message}"
                f"{context_text}"
            ),
            text_format=AgentPlan,
            reasoning={"effort": "low"},
            safety_identifier=safety_identifier,
            store=False,
            verbosity="low",
        )
        if response.output_parsed is None:
            return resolve_plan_context(AgentPlan(intent="unknown"), context)
        return resolve_plan_context(response.output_parsed, context)
