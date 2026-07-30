import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.core_client import CoreAPIClient


def test_core_client_forwards_actor_identity():
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(
            200,
            json=[
                {
                    "id": 3,
                    "name": "Jamie Rivera",
                    "role": "employee",
                }
            ],
        )

    client = CoreAPIClient(
        "http://core.test",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(client.list_time_entries(3))
    asyncio.run(client.close())

    assert seen_headers["x-actor-id"] == "3"
    assert result[0]["id"] == 3


def test_core_client_preserves_authorization_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "Outside actor scope"})

    client = CoreAPIClient(
        "http://core.test",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(client.list_time_entries(3))
    asyncio.run(client.close())

    assert error.value.status_code == 403
    assert error.value.detail == "Outside actor scope"


def test_core_client_routes_extended_read_queries():
    seen_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(200, json=[])

    client = CoreAPIClient(
        "http://core.test",
        transport=httpx.MockTransport(handler),
    )
    asyncio.run(client.list_departments(3))
    asyncio.run(client.list_employees(3))
    asyncio.run(client.list_project_members(3, 1))
    asyncio.run(client.close())

    assert seen_paths == [
        "/departments",
        "/employees",
        "/projects/1/members",
    ]
