"""Typed-enough HTTP boundary between MCP tools and the demo Core API."""

from __future__ import annotations

import os
from typing import Any

import httpx


class CoreAPIError(RuntimeError):
    """Expose a safe Core API error without leaking transport internals."""


class CoreAPIClient:
    """Call the policy-enforcing Core API; this service never accesses SQLite."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("DEMO_CORE_API_BASE_URL", "http://localhost:8001")).rstrip("/")
        self.transport = transport

    async def request(
        self,
        method: str,
        path: str,
        actor_id: int,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Forward one request with the explicit fictional demo identity."""

        if actor_id < 1:
            raise ValueError("actor_id must be a positive demo employee ID")
        async with httpx.AsyncClient(
            base_url=self.base_url,
            transport=self.transport,
            timeout=10.0,
        ) as client:
            try:
                response = await client.request(
                    method,
                    path,
                    headers={"X-Actor-ID": str(actor_id)},
                    params={key: value for key, value in (params or {}).items() if value is not None},
                    json=json,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                try:
                    detail = exc.response.json().get("detail", "Core API rejected the request")
                except (ValueError, AttributeError):
                    detail = "Core API rejected the request"
                raise CoreAPIError(f"Core API returned {exc.response.status_code}: {detail}") from exc
            except httpx.HTTPError as exc:
                raise CoreAPIError("Core API is unavailable") from exc
        return response.json()

    async def get(self, path: str, actor_id: int, **params: Any) -> Any:
        return await self.request("GET", path, actor_id, params=params)

    async def post(
        self,
        path: str,
        actor_id: int,
        body: dict[str, Any],
    ) -> Any:
        return await self.request("POST", path, actor_id, json=body)
