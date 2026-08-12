# Observability

AI API exposes:

- `/health` for liveness;
- `/ready` for Core connectivity and policy-index readiness;
- `/observability` for a JSON process snapshot;
- `/metrics` for Prometheus text metrics;
- `X-Request-ID` on every response.

Structured request logs include only request ID, method, route path, status,
and duration. Chat metrics include the planned intent. They exclude prompts,
answers, actor IDs, headers, workforce records, policy excerpts, and
confirmation tokens.

Confirmed Core writes and Agent executions have separate audit surfaces. Core
write audit preserves fictional business mutation metadata. `/agent-audit` is
admin-only and persists only request ID, actor role, mode, intent, tool names,
status, authorization outcome, latency, and timestamp. It deliberately omits
actor identity, prompts, answers, tool payloads, policy excerpts, and tokens.

Metrics are intentionally process-local for the standalone demo. A production
adapter would export OpenTelemetry signals to a controlled backend with
retention and access policies, but that infrastructure is outside this
publication.
