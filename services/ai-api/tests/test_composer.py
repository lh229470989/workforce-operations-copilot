import asyncio
import json
from datetime import date, datetime

from app.composer import OpenAIComposer
from app.schemas import AgentPlan, ConfirmationCard, ExecutionResult


class FakeResponses:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_text": "自然生成的回答"})()


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_llm_composer_grounds_answer_without_exposing_confirmation_token():
    composer = OpenAIComposer.__new__(OpenAIComposer)
    composer._client = FakeOpenAIClient()
    composer._model = "gpt-5.6-terra"
    composer._instructions = "composer-test-v1"
    result = ExecutionResult(
        message="I prepared a dry-run draft.",
        data={"hours": "2.00", "project_name": "Apollo"},
        confirmation=ConfirmationCard(
            action="create_time_entry",
            preview={"hours": "2.00", "project_name": "Apollo"},
            confirmation_token="must-not-reach-the-model",
            expires_at=datetime(2026, 7, 22, 12, 15),
            confirm_path="/actions/must-not-reach-the-model/confirm",
        ),
    )

    answer = asyncio.run(
        composer.compose(
            "帮我记录两小时",
            AgentPlan(intent="draft_time_entry"),
            result,
            None,
            3,
        )
    )
    call = composer._client.responses.calls[0]
    payload = json.loads(call["input"])

    assert answer == "自然生成的回答"
    assert call["store"] is False
    assert call["reasoning"] == {"effort": "low"}
    assert len(call["safety_identifier"]) == 32
    assert "must-not-reach-the-model" not in call["input"]
    assert payload["authorized_execution"]["dry_run_confirmation"] == {
        "action": "create_time_entry",
        "preview": {"hours": "2.00", "project_name": "Apollo"},
        "expires_at": "2026-07-22T12:15:00",
    }


def test_dashscope_composer_uses_minimal_responses_parameters():
    composer = OpenAIComposer.__new__(OpenAIComposer)
    composer._client = FakeOpenAIClient()
    composer._model = "qwen-flash"
    composer._instructions = "composer-test-v1"
    composer._is_dashscope = True

    answer = asyncio.run(
        composer.compose(
            "你好",
            AgentPlan(intent="greeting"),
            ExecutionResult(message="你好"),
            None,
            1,
        )
    )
    call = composer._client.responses.calls[0]

    assert answer == "自然生成的回答"
    assert call["extra_body"] == {"enable_thinking": False}
    assert "reasoning" not in call
    assert "safety_identifier" not in call
    assert "verbosity" not in call


def test_composer_serializes_python_dates_in_authorized_results():
    composer = OpenAIComposer.__new__(OpenAIComposer)
    composer._client = FakeOpenAIClient()
    composer._model = "qwen-flash"
    composer._instructions = "composer-test-v1"
    composer._is_dashscope = True

    asyncio.run(
        composer.compose(
            "记录今天的工时",
            AgentPlan(intent="draft_time_entry", work_date=date(2026, 8, 2)),
            ExecutionResult(
                message="Dry run prepared.",
                data={"work_date": date(2026, 8, 2)},
            ),
            None,
            3,
        )
    )
    payload = json.loads(composer._client.responses.calls[0]["input"])

    assert payload["authorized_execution"]["data"]["work_date"] == "2026-08-02"


def test_chart_answer_defers_visual_rendering_to_the_web_component():
    composer = OpenAIComposer.__new__(OpenAIComposer)
    composer._client = FakeOpenAIClient()
    composer._model = "qwen-flash"
    composer._instructions = "composer-test-v1"
    composer._is_dashscope = True

    answer = asyncio.run(
        composer.compose(
            "显示我 2026 年 7 月按项目统计的工时图表",
            AgentPlan(intent="monthly_chart"),
            ExecutionResult(
                message="Here are your monthly hours.",
                data={
                    "type": "bar",
                    "title": "Monthly hours by project",
                    "x_key": "month",
                    "series_key": "project",
                    "value_key": "hours",
                    "rows": [
                        {"month": "2026-07", "project": "Apollo", "hours": "15.50"}
                    ],
                },
            ),
            None,
            3,
        )
    )

    assert answer == (
        "已生成按项目统计的月度工时图表，共 1 个数据项。"
        "图表数据来自当前角色可见的工时记录。"
    )
    assert "```" not in answer
    assert composer._client.responses.calls == []


def test_export_answer_never_allows_the_model_to_invent_a_download_link():
    composer = OpenAIComposer.__new__(OpenAIComposer)
    composer._client = FakeOpenAIClient()
    composer._model = "qwen-flash"
    composer._instructions = "composer-test-v1"
    composer._is_dashscope = True

    answer = asyncio.run(
        composer.compose(
            "Download my submitted entries as CSV",
            AgentPlan(intent="export_report"),
            ExecutionResult(
                message="Export ready.",
                data={"type": "report_export", "row_count": 2, "filters": {}},
            ),
            None,
            3,
        )
    )

    assert answer == "Your role-scoped CSV export is ready with 2 matching time entries."
    assert "http" not in answer
    assert composer._client.responses.calls == []


def test_time_entry_list_answer_defers_rows_to_structured_web_table():
    composer = OpenAIComposer.__new__(OpenAIComposer)
    composer._client = FakeOpenAIClient()
    composer._model = "qwen-flash"
    composer._instructions = "composer-test-v1"
    composer._is_dashscope = True

    answer = asyncio.run(
        composer.compose(
            "看下目前所有填的工时",
            AgentPlan(intent="time_entries"),
            ExecutionResult(
                message="Found one entry.",
                data=[{
                    "id": 1, "project_name": "Apollo", "work_date": "2026-08-11",
                    "hours": "1.25", "description": "Validated", "status": "submitted",
                }],
            ),
            None,
            3,
        )
    )

    assert answer == "在你当前角色的权限范围内，共找到 1 条工时记录。"
    assert composer._client.responses.calls == []
