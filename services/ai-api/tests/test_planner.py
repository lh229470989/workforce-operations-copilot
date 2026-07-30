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


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()

    async def close(self):
        return None


def test_openai_planner_uses_structured_responses_and_safety_identifier():
    planner = OpenAIPlanner.__new__(OpenAIPlanner)
    planner._client = FakeOpenAIClient()
    planner._model = "gpt-5.6-terra"

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
