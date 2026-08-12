import asyncio
from datetime import date
from decimal import Decimal

from app.planner import LocalPlanner


TODAY = date(2026, 7, 22)


def plan(message: str):
    return asyncio.run(LocalPlanner().plan(message, TODAY, 3))


def test_relative_date_ranges():
    assert plan("Show my time entries yesterday").model_dump(
        include={"start_date", "end_date"}
    ) == {
        "start_date": date(2026, 7, 21),
        "end_date": date(2026, 7, 21),
    }
    assert plan("显示我上个月的工时记录").model_dump(
        include={"start_date", "end_date"}
    ) == {
        "start_date": date(2026, 6, 1),
        "end_date": date(2026, 6, 30),
    }
    assert plan("Show my time entries for the last 30 days").model_dump(
        include={"start_date", "end_date", "limit"}
    ) == {
        "start_date": date(2026, 6, 23),
        "end_date": date(2026, 7, 22),
        "limit": None,
    }


def test_unknown_project_name_is_forwarded_for_scoped_resolution():
    result = plan("Show time entries on Orion this week")
    assert result.intent == "time_entries"
    assert result.project_name == "Orion"


def test_chinese_status_and_limit_are_parsed():
    result = plan("显示最近 2 条已提交工时记录")
    assert result.intent == "time_entries"
    assert result.entry_status == "submitted"
    assert result.limit == 2


def test_local_fallback_handles_basic_social_turns():
    assert plan("你好").intent == "greeting"
    assert plan("Thanks!").intent == "greeting"


def test_explicit_chinese_write_remains_a_dry_run_draft():
    result = plan(
        "帮我为 Apollo 项目记录今天 2 小时，描述是整理 API 文档"
    )

    assert result.intent == "draft_time_entry"
    assert result.project_name == "Apollo"
    assert result.work_date == TODAY
    assert result.hours == Decimal("2")
    assert result.description == "整理 API 文档"


def test_local_planner_supports_suggestions_and_explicit_batch_items():
    suggestion = plan("给我一些今天的智能填报建议")
    assert suggestion.intent == "suggest_time_entries"
    assert suggestion.work_date == TODAY

    batch = plan(
        "批量填报：2026-07-23 Apollo 2 小时，描述：整理接口文档；"
        "2026-07-24 Apollo 3 小时，描述：补充接口测试"
    )
    assert batch.intent == "draft_time_entries_batch"
    assert len(batch.batch_entries) == 2
    assert batch.batch_entries[0].project_name == "Apollo"
    assert batch.batch_entries[0].hours == Decimal("2")
    assert batch.batch_entries[1].description == "补充接口测试"


def test_local_planner_requires_an_exact_entry_for_approval_action():
    action = plan("批准工时记录 2，备注：内容完整")
    assert action.intent == "decide_time_entry"
    assert action.time_entry_id == 2
    assert action.approval_decision == "approved"
    assert action.approval_comment == "内容完整"

    question = plan("Can I approve my team's pending time entries?")
    assert question.intent == "pending_team"


def test_local_planner_understands_weekly_report_range():
    result = plan("Generate my weekly report for this week")
    assert result.intent == "weekly_report"
    assert result.start_date == date(2026, 7, 20)


def test_local_planner_builds_bounded_read_only_comparison_steps():
    result = plan("Compare Apollo and Beacon hours this week")
    assert result.intent == "compare_analysis"
    assert [step.label for step in result.analysis_steps] == ["Apollo", "Beacon"]
    assert all(step.start_date == date(2026, 7, 20) for step in result.analysis_steps)

    weeks = plan("Compare Apollo this week and last week")
    assert [step.label for step in weeks.analysis_steps] == [
        "Last week",
        "This week",
    ]


def test_local_planner_emits_declarative_analytics_but_rejects_raw_sql():
    safe = plan("SQL analysis: group hours by status this week")
    assert safe.intent == "safe_sql_analysis"
    assert safe.analytics_query.dimension == "status"
    assert safe.analytics_query.metric == "hours"
    assert safe.analytics_query.start_date == date(2026, 7, 20)

    raw = plan("SQL analysis: SELECT * FROM employees; DROP TABLE employees")
    assert raw.intent == "safe_sql_analysis"
    assert raw.analytics_query is None
