import asyncio
from datetime import date

from app.planner import OpenAIPlanner
from app.schemas import AgentPlan


class FakeResponses:
    def __init__(self):
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "Response",
            (),
            {"output_parsed": AgentPlan(intent="list_projects")},
        )()


class IncompleteDraftResponses:
    def __init__(self):
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "Response",
            (),
            {"output_parsed": AgentPlan(intent="draft_time_entry")},
        )()


class MisroutedAnalyticsResponses:
    async def parse(self, **kwargs):
        return type(
            "Response",
            (),
            {"output_parsed": AgentPlan(intent="compare_analysis")},
        )()


class FailingResponses:
    async def parse(self, **kwargs):
        raise ValueError("malformed provider output")


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()

    async def close(self):
        return None


class FailingOpenAIClient:
    def __init__(self):
        self.responses = FailingResponses()


class IncompleteDraftOpenAIClient:
    def __init__(self):
        self.responses = IncompleteDraftResponses()


class MisroutedAnalyticsOpenAIClient:
    def __init__(self):
        self.responses = MisroutedAnalyticsResponses()


def test_openai_planner_uses_structured_responses_and_safety_identifier():
    planner = OpenAIPlanner.__new__(OpenAIPlanner)
    planner._client = FakeOpenAIClient()
    planner._model = "gpt-5.6-terra"
    planner._instructions = "planner-test-v1"

    plan = asyncio.run(
        planner.plan("Which projects can I see?", date(2026, 7, 29), 3)
    )
    call = planner._client.responses.calls[0]

    assert plan.intent == "list_projects"
    assert call["model"] == "gpt-5.6-terra"
    assert call["text_format"] is AgentPlan
    assert call["reasoning"] == {"effort": "low"}
    assert call["store"] is False
    assert call["verbosity"] == "low"
    assert len(call["safety_identifier"]) == 32


def test_dashscope_planner_disables_thinking_for_structured_output():
    planner = OpenAIPlanner.__new__(OpenAIPlanner)
    planner._client = FakeOpenAIClient()
    planner._model = "qwen-flash"
    planner._instructions = "planner-test-v1"
    planner._is_dashscope = True

    plan = asyncio.run(planner.plan("你好", date(2026, 8, 2), 1))
    call = planner._client.responses.calls[0]

    assert plan.intent == "list_projects"
    assert call["extra_body"] == {"enable_thinking": False}
    assert "reasoning" not in call
    assert "safety_identifier" not in call
    assert "verbosity" not in call


def test_openai_planner_falls_back_safely_on_provider_failure():
    planner = OpenAIPlanner.__new__(OpenAIPlanner)
    planner._client = FailingOpenAIClient()
    planner._model = "qwen-flash"
    planner._instructions = "planner-test-v1"
    planner._is_dashscope = True

    plan = asyncio.run(planner.plan("你好", date(2026, 8, 2), 1))

    assert plan.intent == "greeting"


def test_openai_planner_fills_exact_write_fields_from_current_message():
    planner = OpenAIPlanner.__new__(OpenAIPlanner)
    planner._client = IncompleteDraftOpenAIClient()
    planner._model = "qwen3.5-plus"
    planner._instructions = "planner-test-v1"
    planner._is_dashscope = True

    plan = asyncio.run(
        planner.plan(
            "帮我为 Apollo 项目记录今天 2 小时，描述是整理 API 文档",
            date(2026, 8, 2),
            3,
        )
    )

    assert plan.intent == "draft_time_entry"
    assert plan.project_name == "Apollo"
    assert plan.work_date == date(2026, 8, 2)
    assert str(plan.hours) == "2"
    assert plan.description == "整理 API 文档"


def test_deterministic_safe_analytics_overrides_model_misrouting():
    planner = OpenAIPlanner.__new__(OpenAIPlanner)
    planner._client = MisroutedAnalyticsOpenAIClient()
    planner._model = "qwen-flash"
    planner._instructions = "planner-test-v1"
    planner._is_dashscope = True

    plan = asyncio.run(
        planner.plan(
            "用安全分析按状态统计我上周的工时",
            date(2026, 8, 11),
            3,
        )
    )

    assert plan.intent == "safe_sql_analysis"
    assert plan.analytics_query is not None
    assert plan.analytics_query.dimension == "status"
    assert plan.analytics_query.start_date == date(2026, 8, 3)
    assert plan.analytics_query.end_date == date(2026, 8, 9)
