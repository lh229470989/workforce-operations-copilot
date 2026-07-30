import asyncio
from datetime import date

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
