from __future__ import annotations

import json

import httpx
import pytest

from app.core_client import CoreAPIClient, CoreAPIError
from app.server import create_server


def mock_core(request: httpx.Request) -> httpx.Response:
    """Minimal fake that also verifies every MCP call carries actor identity."""

    assert request.headers["X-Actor-ID"] == "1"
    if request.url.path == "/me":
        return httpx.Response(200, json={"id": 1, "name": "Jamie Chen", "role": "employee"})
    if request.url.path == "/projects":
        return httpx.Response(200, json=[{"id": 1, "name": "Apollo"}])
    if request.url.path == "/time-entries/dry-run":
        return httpx.Response(
            201,
            json={
                "dry_run": True,
                "action": "create_time_entry",
                "preview": {"project_name": "Apollo", "hours": "2.00"},
                "confirmation_token": "server-secret-token",
                "expires_at": "2026-08-12T12:00:00Z",
            },
        )
    return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture
def server():
    transport = httpx.MockTransport(mock_core)
    return create_server(CoreAPIClient("http://core.test", transport=transport))


@pytest.mark.asyncio
async def test_protocol_catalog_has_tools_resources_and_prompts(server):
    tools = await server.list_tools()
    resources = await server.list_resources()
    prompts = await server.list_prompts()

    names = {tool.name for tool in tools}
    assert {"get_current_user", "query_safe_analytics", "create_time_entry_dry_run"} <= names
    assert any(str(resource.uri) == "acmeworks://capabilities" for resource in resources)
    assert {prompt.name for prompt in prompts} >= {"weekly_report", "prepare_time_entry"}


@pytest.mark.asyncio
async def test_read_tool_returns_structured_scoped_data(server):
    result = await server.call_tool("get_current_user", {"actor_id": 1})

    assert result.is_error is False
    assert result.structured_content["name"] == "Jamie Chen"


@pytest.mark.asyncio
async def test_dry_run_hides_confirmation_token_from_model_content(server):
    result = await server.call_tool(
        "create_time_entry_dry_run",
        {
            "actor_id": 1,
            "project_id": 1,
            "work_date": "2026-08-12",
            "hours": "2",
            "description": "Documented MCP boundary",
        },
    )

    visible_text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
    assert "server-secret-token" not in visible_text
    assert "confirmation_token" not in json.dumps(result.structured_content)
    assert result.meta["confirmation"]["token"] == "server-secret-token"


@pytest.mark.asyncio
async def test_core_errors_are_safely_normalized():
    def reject(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "outside actor scope"})

    client = CoreAPIClient("http://core.test", transport=httpx.MockTransport(reject))
    with pytest.raises(CoreAPIError, match="outside actor scope"):
        await client.get("/employees", 1)
