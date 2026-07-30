from typing import Any

import httpx
from fastapi import HTTPException


class CoreAPIClient:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=10,
            transport=transport,
            trust_env=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def get_me(self, actor_id: int) -> dict[str, Any]:
        return await self._request("GET", "/me", actor_id=actor_id)

    async def list_departments(self, actor_id: int) -> list[dict[str, Any]]:
        return await self._request("GET", "/departments", actor_id=actor_id)

    async def list_employees(self, actor_id: int) -> list[dict[str, Any]]:
        return await self._request("GET", "/employees", actor_id=actor_id)

    async def list_projects(self, actor_id: int) -> list[dict[str, Any]]:
        return await self._request("GET", "/projects", actor_id=actor_id)

    async def list_project_members(
        self, actor_id: int, project_id: int
    ) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            f"/projects/{project_id}/members",
            actor_id=actor_id,
        )

    async def list_time_entries(
        self, actor_id: int, **filters: Any
    ) -> list[dict[str, Any]]:
        params = {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in filters.items()
            if value is not None
        }
        return await self._request(
            "GET", "/time-entries", actor_id=actor_id, params=params
        )

    async def get_summary(self, actor_id: int) -> dict[str, Any]:
        return await self._request("GET", "/stats/summary", actor_id=actor_id)

    async def dry_run_time_entry(
        self, actor_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/time-entries/dry-run",
            actor_id=actor_id,
            json=payload,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        actor_id: int | None = None,
        **kwargs: Any,
    ) -> Any:
        headers = kwargs.pop("headers", {})
        if actor_id is not None:
            headers["X-Actor-ID"] = str(actor_id)
        try:
            response = await self._client.request(
                method, path, headers=headers, **kwargs
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503, detail="Demo Core API is unavailable"
            ) from exc

        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            upstream_status = response.status_code
            status_code = upstream_status if upstream_status < 500 else 502
            raise HTTPException(status_code=status_code, detail=detail)
        return response.json()
