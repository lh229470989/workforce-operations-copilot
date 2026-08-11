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

    async def get_weekly_report(
        self, actor_id: int, week_start: Any = None
    ) -> dict[str, Any]:
        params = {}
        if week_start is not None:
            params["week_start"] = (
                week_start.isoformat()
                if hasattr(week_start, "isoformat")
                else week_start
            )
        return await self._request(
            "GET", "/reports/weekly", actor_id=actor_id, params=params
        )

    async def run_safe_analytics(
        self, actor_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST", "/analytics/query", actor_id=actor_id, json=payload
        )

    async def get_time_entry_suggestions(
        self, actor_id: int, target_date: Any = None
    ) -> list[dict[str, Any]]:
        params = {}
        if target_date is not None:
            params["target_date"] = (
                target_date.isoformat()
                if hasattr(target_date, "isoformat")
                else target_date
            )
        return await self._request(
            "GET",
            "/time-entry-suggestions",
            actor_id=actor_id,
            params=params,
        )

    async def dry_run_time_entry(
        self, actor_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/time-entries/dry-run",
            actor_id=actor_id,
            json=payload,
        )

    async def dry_run_time_entry_batch(
        self, actor_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/time-entries/batch/dry-run",
            actor_id=actor_id,
            json=payload,
        )

    async def dry_run_approval(
        self,
        actor_id: int,
        time_entry_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Request a proposal only; confirmation remains outside the agent."""

        return await self._request(
            "POST",
            f"/time-entries/{time_entry_id}/approval/dry-run",
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
