"""Privacy-conscious request metrics and structured operational logging."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from threading import Lock
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
logger = logging.getLogger("acmeworks.ai_api")


class MetricsRegistry:
    """Store low-cardinality process metrics without message or actor content."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Counter[tuple[str, str, int]] = Counter()
        self._chat_intents: Counter[str] = Counter()
        self._request_duration_seconds = 0.0

    def observe_request(
        self, method: str, path: str, status_code: int, duration: float
    ) -> None:
        with self._lock:
            self._requests[(method, path, status_code)] += 1
            self._request_duration_seconds += duration

    def observe_chat(self, intent: str) -> None:
        with self._lock:
            self._chat_intents[intent] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "requests": [
                    {
                        "method": method,
                        "path": path,
                        "status": status,
                        "count": count,
                    }
                    for (method, path, status), count in sorted(
                        self._requests.items()
                    )
                ],
                "chat_intents": dict(sorted(self._chat_intents.items())),
                "request_duration_seconds_total": round(
                    self._request_duration_seconds, 6
                ),
            }

    def render_prometheus(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP acmeworks_http_requests_total HTTP requests handled.",
            "# TYPE acmeworks_http_requests_total counter",
        ]
        for item in snapshot["requests"]:
            lines.append(
                "acmeworks_http_requests_total"
                f'{{method="{item["method"]}",path="{item["path"]}",'
                f'status="{item["status"]}"}} {item["count"]}'
            )
        lines.extend(
            [
                "# HELP acmeworks_chat_intents_total Planned chat intents.",
                "# TYPE acmeworks_chat_intents_total counter",
            ]
        )
        for intent, count in snapshot["chat_intents"].items():
            lines.append(
                f'acmeworks_chat_intents_total{{intent="{intent}"}} {count}'
            )
        lines.extend(
            [
                "# HELP acmeworks_http_request_duration_seconds_total "
                "Cumulative request duration.",
                "# TYPE acmeworks_http_request_duration_seconds_total counter",
                "acmeworks_http_request_duration_seconds_total "
                f'{snapshot["request_duration_seconds_total"]}',
            ]
        )
        return "\n".join(lines) + "\n"


def install_observability(app: FastAPI, metrics: MetricsRegistry) -> None:
    """Install request IDs, safe headers, metrics, and metadata-only logs."""

    @app.middleware("http")
    async def observe_request(request: Request, call_next):
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid4())
        )
        # Downstream handlers use this safe identifier for metadata-only audit.
        request.state.request_id = request_id
        started = perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
        finally:
            duration = perf_counter() - started
            metrics.observe_request(
                request.method, request.url.path, status_code, duration
            )
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "duration_ms": round(duration * 1000, 2),
                    },
                    separators=(",", ":"),
                )
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        # Swagger UI loads its bundled assets from jsDelivr, while API
        # responses otherwise remain non-embeddable and non-cacheable.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"
        )
        response.headers["X-Frame-Options"] = "DENY"
        return response
