import json
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import ValidationError

from .conversation_context import (
    infer_local_conversation_relation,
    resolve_plan_context,
)
from .schemas import (
    AnalysisStep,
    AgentPlan,
    AnalyticsQuerySpec,
    PlannerContext,
    TimeEntryDraftItem,
)

PROJECT_NAMES = ("Apollo", "Beacon", "Cedar")
logger = logging.getLogger(__name__)

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


def _parse_batch_entries(text: str, today: date) -> list[TimeEntryDraftItem]:
    """Parse explicit semicolon/newline-separated items for safe fallback."""

    entries: list[TimeEntryDraftItem] = []
    for segment in re.split(r"[;；\n]+", text):
        project_name = _extract_project_name(segment)
        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", segment)
        hours_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|小时)",
            segment,
            re.IGNORECASE,
        )
        description_match = re.search(
            r"(?:description|描述|备注)(?:\s*(?:is|是|为|[:：]))?\s*(.+)$",
            segment,
            re.IGNORECASE,
        )
        relative_today = "today" in segment.lower() or "今天" in segment
        if not any((project_name, date_match, hours_match, description_match)):
            continue
        entries.append(
            TimeEntryDraftItem(
                project_name=project_name,
                work_date=(
                    date.fromisoformat(date_match.group())
                    if date_match
                    else today if relative_today else None
                ),
                hours=(
                    Decimal(hours_match.group(1)) if hours_match else None
                ),
                description=(
                    description_match.group(1).strip()
                    if description_match
                    else None
                ),
            )
        )
    return entries


def _parse_approval_action(
    text: str,
) -> tuple[int | None, str | None, str | None]:
    """Extract only an explicitly named entry, decision, and optional comment."""

    lowered = text.lower()
    entry_match = re.search(
        r"(?:time\s*entry|entry|record|工时记录|工时|记录)\s*#?\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    if entry_match is None:
        entry_match = re.search(r"#(\d+)", text)
    if any(word in lowered for word in ("reject", "decline")) or any(
        word in text for word in ("驳回", "拒绝")
    ):
        decision = "rejected"
    elif any(word in lowered for word in ("approve", "accept")) or any(
        word in text for word in ("批准", "通过")
    ):
        decision = "approved"
    else:
        decision = None
    comment_match = re.search(
        r"(?:comment|reason|备注|意见)(?:\s*(?:is|是|为|[:：]))?\s*(.+)$",
        text,
        re.IGNORECASE,
    )
    return (
        int(entry_match.group(1)) if entry_match else None,
        decision,
        comment_match.group(1).strip() if comment_match else None,
    )


def _parse_comparison_steps(text: str, today: date) -> list[AnalysisStep]:
    """Build safe offline comparison slices from explicit projects or weeks."""

    lowered = text.casefold()
    projects = [name for name in PROJECT_NAMES if name.casefold() in lowered]
    pair = re.search(
        r"\bcompare\s+([A-Za-z][\w-]*)\s+(?:and|vs\.?|versus)\s+([A-Za-z][\w-]*)",
        text,
        re.IGNORECASE,
    )
    if pair:
        projects = [pair.group(1), pair.group(2)]
    status = _entry_status(text, lowered)
    if len(projects) >= 2:
        start, end = _read_date_range(text, lowered, today, [])
        return [
            AnalysisStep(
                label=name,
                project_name=name,
                entry_status=status,
                start_date=start,
                end_date=end,
            )
            for name in projects[:4]
        ]
    if len(projects) == 1 and (
        ("this week" in lowered and "last week" in lowered)
        or ("本周" in text and "上周" in text)
    ):
        this_start = today - timedelta(days=today.weekday())
        return [
            AnalysisStep(
                label="Last week",
                project_name=projects[0],
                entry_status=status,
                start_date=this_start - timedelta(days=7),
                end_date=this_start - timedelta(days=1),
            ),
            AnalysisStep(
                label="This week",
                project_name=projects[0],
                entry_status=status,
                start_date=this_start,
                end_date=today,
            ),
        ]
    return []


def _parse_analytics_spec(
    text: str,
    start_date: date | None,
    end_date: date | None,
    entry_status: str | None,
) -> AnalyticsQuerySpec:
    lowered = text.casefold()
    if any(word in lowered for word in ("status", "状态")):
        dimension = "status"
    elif any(word in lowered for word in ("employee", "person", "员工", "人员")):
        dimension = "employee"
    elif any(word in lowered for word in ("month", "monthly", "月份", "月度")):
        dimension = "month"
    elif any(word in lowered for word in ("day", "date", "每日", "日期")):
        dimension = "work_date"
    else:
        dimension = "project"
    metric = (
        "entry_count"
        if any(
            phrase in lowered
            for phrase in ("entry count", "record count", "number of entries", "记录数", "条数")
        )
        else "hours"
    )
    return AnalyticsQuerySpec(
        dimension=dimension,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        entry_status=entry_status,
        project_name=_extract_project_name(text),
    )


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

        # Explicit memory commands are parsed locally as a safety boundary.
        # The model may classify the intent, but it cannot invent the value
        # being persisted or select another actor's record.
        if any(phrase in lowered for phrase in ("what do you remember", "list my memories", "show my memories")) or any(
            phrase in text for phrase in ("你记住了什么", "查看我的记忆", "列出我的记忆")
        ):
            return AgentPlan(intent="list_memories")
        remember_match = re.match(
            r"(?:please\s+)?(?:remember|记住)(?:\s+that|[:：])?\s*(.+)$",
            text,
            re.IGNORECASE,
        )
        if remember_match:
            value = remember_match.group(1).strip()
            category = (
                "reporting_preference"
                if any(word in lowered for word in ("report", "weekly", "报表", "周报"))
                else "collaboration_preference"
                if any(word in lowered for word in ("collabor", "meeting", "协作", "会议"))
                else "work_preference"
            )
            return AgentPlan(intent="remember_memory", memory_category=category, memory_value=value)
        forget_match = re.match(
            r"(?:please\s+)?(?:forget|忘记|删除记忆)(?:\s+that|[:：])?\s*(.+)$",
            text,
            re.IGNORECASE,
        )
        if forget_match:
            return AgentPlan(intent="forget_memory", memory_value=forget_match.group(1).strip())

        lifecycle_match = re.search(
            r"(?:time\s*entry|entry|record|工时记录|记录)\s*#?\s*(\d+)",
            lowered,
        ) or re.search(r"(?:编号|id)\s*#?\s*(\d+)", lowered)
        lifecycle_action = next(
            (
                action
                for action, markers in (
                    ("submit", ("submit", "提交")),
                    ("withdraw", ("withdraw", "撤回")),
                    ("delete", ("delete", "remove", "删除")),
                    ("update", ("edit", "update", "修改", "编辑")),
                )
                if any(marker in lowered for marker in markers)
            ),
            None,
        )
        if lifecycle_match and lifecycle_action:
            hours_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|小时)", lowered)
            description_match = re.search(
                r"(?:description|描述|备注)(?:\s*(?:is|是|为|[:：]))?\s*(.+)$",
                text,
                re.IGNORECASE,
            )
            return AgentPlan(
                intent="manage_time_entry",
                time_entry_id=int(lifecycle_match.group(1)),
                lifecycle_action=lifecycle_action,
                project_name=project_name if lifecycle_action == "update" else None,
                work_date=dates[0] if lifecycle_action == "update" and dates else None,
                hours=Decimal(hours_match.group(1)) if hours_match else None,
                description=description_match.group(1).strip() if description_match else None,
            )

        # The local planner is an offline fallback, so exact social phrases are
        # handled here without pretending to provide open-ended model chat.
        normalized = re.sub(r"[\s!！,.，。?？]+", "", lowered)
        if normalized in {
            "hello",
            "hi",
            "hey",
            "你好",
            "您好",
            "嗨",
            "谢谢",
            "thanks",
            "thankyou",
            "再见",
            "bye",
        }:
            return AgentPlan(intent="greeting")

        if any(word in lowered for word in ("compare", "versus", " vs ")) or any(
            word in text for word in ("对比", "比较")
        ):
            return AgentPlan(
                intent="compare_analysis",
                analysis_steps=_parse_comparison_steps(text, today),
            )

        analytics_request = any(
            phrase in lowered
            for phrase in (
                "sql analysis",
                "sql agent",
                "analytics query",
                "group hours by",
                "安全分析",
                "数据分析",
                "按项目统计",
                "按状态统计",
            )
        )
        raw_sql_markers = re.search(
            r"(?:;|--|\bselect\b|\bdrop\b|\binsert\b|\bupdate\b|\bdelete\b|\bpragma\b)",
            lowered,
        )
        if analytics_request and raw_sql_markers is not None:
            return AgentPlan(intent="safe_sql_analysis", analytics_query=None)
        if analytics_request:
            return AgentPlan(
                intent="safe_sql_analysis",
                analytics_query=_parse_analytics_spec(
                    text, start_date, end_date, entry_status
                ),
            )

        if any(
            phrase in lowered
            for phrase in (
                "suggest time",
                "recommend time",
                "work suggestions",
                "填报建议",
                "工时建议",
                "推荐填报",
                "智能填报",
            )
        ):
            work_date = start_date if start_date == end_date else None
            return AgentPlan(
                intent="suggest_time_entries", work_date=work_date
            )

        if ("batch" in lowered or "批量" in text) and any(
            phrase in lowered
            for phrase in (
                "draft",
                "log",
                "record",
                "填报",
                "记录",
                "登记",
            )
        ):
            return AgentPlan(
                intent="draft_time_entries_batch",
                batch_entries=_parse_batch_entries(text, today),
            )

        hours_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|小时)", lowered
        )
        write_phrase = any(
            phrase in lowered
            for phrase in (
                "draft",
                "log time",
                "record time",
                "add time",
                "草稿",
                "补工时",
                "填报",
                "登记",
            )
        )
        # Chinese "记录" may be a verb (create) or a noun (records). A stated
        # duration distinguishes an explicit write from a history query.
        write_phrase = write_phrase or (
            "记录" in text and hours_match is not None
        )
        if write_phrase:
            description_match = re.search(
                r"(?:description|描述|备注)(?:\s*(?:is|是|为|[:：]))?\s*(.+)$",
                text,
                re.IGNORECASE,
            )
            if description_match is None:
                description_match = re.search(r"[:：]\s*(.+)$", text)
            work_date = dates[0] if dates else None
            if work_date is None and start_date == end_date:
                work_date = start_date
            return AgentPlan(
                intent="draft_time_entry",
                project_name=project_name,
                work_date=work_date,
                hours=(
                    Decimal(hours_match.group(1))
                    if hours_match is not None
                    else None
                ),
                description=(
                    description_match.group(1).strip()
                    if description_match
                    else None
                ),
            )

        export_requested = any(
            phrase in lowered
            for phrase in ("export", "download", "csv", "导出", "下载")
        )
        report_subject = any(
            phrase in lowered
            for phrase in ("report", "time entries", "timesheet", "工时", "报表")
        )
        if export_requested and report_subject:
            return AgentPlan(
                intent="export_report",
                project_name=project_name,
                start_date=start_date,
                end_date=end_date,
                entry_status=entry_status,
            )

        if (
            any(phrase in lowered for phrase in ("weekly report", "week report"))
            or "周报" in text
        ):
            return AgentPlan(
                intent="weekly_report",
                start_date=start_date,
                end_date=end_date,
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

        batch_approval = re.search(
            r"(?:entries|records|记录)\s*#?\s*((?:\d+\s*[,，、]\s*)+\d+)",
            lowered,
        )
        batch_decision = (
            "rejected"
            if any(word in lowered for word in ("reject", "拒绝", "驳回"))
            else "approved"
            if any(word in lowered for word in ("approve", "批准", "通过"))
            else None
        )
        if batch_approval and batch_decision:
            return AgentPlan(
                intent="decide_time_entries",
                time_entry_ids=[int(value) for value in re.findall(r"\d+", batch_approval.group(1))],
                approval_decision=batch_decision,
            )

        entry_id, decision, comment = _parse_approval_action(text)
        if entry_id is not None and decision is not None:
            return AgentPlan(
                intent="decide_time_entry",
                time_entry_id=entry_id,
                approval_decision=decision,
                approval_comment=comment,
            )

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
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        *,
        instructions: str,
    ) -> None:
        client_options = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url
        self._client = AsyncOpenAI(
            **client_options,
            timeout=45.0,
            max_retries=1,
        )
        self._model = model
        self._instructions = instructions
        self._is_dashscope = bool(
            base_url
            and (
                "dashscope." in base_url
                or ".maas.aliyuncs.com" in base_url
            )
        )

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
        request: dict[str, Any] = {
            "model": self._model,
            "instructions": self._instructions,
            "input": (
                f"Today is {today.isoformat()}.\nUser request: {message}"
                f"{context_text}"
            ),
            "text_format": AgentPlan,
            "max_output_tokens": 1000,
            "store": False,
        }
        if getattr(self, "_is_dashscope", False):
            # DashScope enables thinking for some Qwen aliases. Structured
            # output requires message format, so planning disables thinking.
            request["extra_body"] = {"enable_thinking": False}
        else:
            request.update(
                {
                    "reasoning": {"effort": "low"},
                    "safety_identifier": safety_identifier,
                    "verbosity": "low",
                }
            )
        try:
            response = await self._client.responses.parse(**request)
        except Exception as exc:
            # Provider failures and malformed structured output must not turn
            # an otherwise safe chat request into an internal server error.
            validation_fields = ""
            if isinstance(exc, ValidationError):
                validation_fields = ",".join(
                    ".".join(str(part) for part in error["loc"])
                    + ":"
                    + error["type"]
                    for error in exc.errors(include_input=False)
                )
            logger.warning(
                "llm_planning_failed error_type=%s fields=%s",
                type(exc).__name__,
                validation_fields or "none",
            )
            return await LocalPlanner().plan(message, today, actor_id, context)
        if response.output_parsed is None:
            return resolve_plan_context(AgentPlan(intent="unknown"), context)
        parsed_plan = response.output_parsed
        # Analytics has a deterministic same-message safety parser. Give it
        # precedence over the provider-selected intent so model variance can
        # never turn an explicit safe-analysis or raw-SQL-shaped request into
        # a different tool plan.
        local_guard_plan = await LocalPlanner().plan(
            message, today, actor_id, context
        )
        if local_guard_plan.intent in {
            "manage_time_entry",
            "decide_time_entries",
            "export_report",
            "remember_memory",
            "list_memories",
            "forget_memory",
        }:
            parsed_plan = local_guard_plan
        elif local_guard_plan.intent == "safe_sql_analysis":
            parsed_plan = local_guard_plan
        elif parsed_plan.intent == "safe_sql_analysis":
            # A provider-only analytics classification is not enough to
            # authorize a query specification. Unsupported wording therefore
            # reaches the safe refusal path with no executable specification.
            parsed_plan = parsed_plan.model_copy(update={"analytics_query": None})
        elif parsed_plan.intent == "draft_time_entry":
            # For writes, exact values visible in the current message outrank
            # model omissions. This resolver only fills fields parsed from the
            # same request; it never inherits write values from conversation.
            local_plan = local_guard_plan
            if local_plan.intent == "draft_time_entry":
                parsed_plan = parsed_plan.model_copy(
                    update={
                        field: value
                        for field in (
                            "project_name",
                            "work_date",
                            "hours",
                            "description",
                        )
                        if (value := getattr(local_plan, field)) is not None
                    }
                )
        elif parsed_plan.intent == "draft_time_entries_batch":
            local_plan = local_guard_plan
            if (
                local_plan.intent == "draft_time_entries_batch"
                and local_plan.batch_entries
            ):
                parsed_plan = parsed_plan.model_copy(
                    update={"batch_entries": local_plan.batch_entries}
                )
        elif parsed_plan.intent == "decide_time_entry":
            # Approval authorization must be based on an exact ID and decision
            # present in this message, never on a model guess or prior turn.
            entry_id, decision, comment = _parse_approval_action(message)
            parsed_plan = parsed_plan.model_copy(
                update={
                    "time_entry_id": entry_id,
                    "approval_decision": decision,
                    "approval_comment": comment,
                }
            )
        elif parsed_plan.intent == "compare_analysis":
            # Deterministically parsed slices from this message override model
            # renderings when available; all other slices still face server
            # validation before any tool executes.
            local_steps = _parse_comparison_steps(message, today)
            if local_steps:
                parsed_plan = parsed_plan.model_copy(
                    update={"analysis_steps": local_steps}
                )
        return resolve_plan_context(parsed_plan, context)
