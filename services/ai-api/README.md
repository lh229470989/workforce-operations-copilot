# AcmeWorks AI API

This service provides a role-aware chat facade over the fictional Demo Core API.
It uses a LangGraph workflow with three stages: plan, execute a bounded tool, and
compose a structured response for the web client.

Role-scoped read capabilities are registered in a separate query layer rather
than embedded in the LangGraph workflow. The graph retains orchestration and
the write boundary, while the registry owns read execution.

## Safety boundary

- The caller supplies only `X-Actor-ID`; roles are loaded and enforced by the
  Demo Core API.
- Read results inherit the Core API's employee, manager, and admin scope.
- The only data-changing tool exposed here calls the Core API's dry-run route.
- The AI API never confirms a token and exposes no approval write tool.
- Missing draft fields cause a clarification response; the planner must not
  invent project, date, hours, or description.

## Modes

`AI_MODE=local` is the default and requires no model credentials. It provides a
deterministic English/Chinese planner for the documented demo prompts and
common relative date ranges.

`AI_MODE=auto` uses OpenAI when `OPENAI_API_KEY` is present and otherwise uses
the local planner. `AI_MODE=openai` requires the key. The default hosted model
is `gpt-5.6-terra` and can be changed with `OPENAI_MODEL`.

The OpenAI mode uses the Responses API for structured intent planning. Tool
execution and authorization remain in application code.

## Conversation and actor context

Each chat response returns an actor-bound `session_id`. The service keeps at
most 10 turns for 30 minutes by default. This short memory supports safe read
follow-ups such as `What about Beacon?` and `Only show submitted entries`.
Configure the limits with `SESSION_TTL_SECONDS` and `SESSION_MAX_TURNS`.

The session is process-local and is not long-term user memory. Every request
refreshes authoritative fictional actor context from Core API: role, visible
departments, visible projects, and five recent time entries. A session cannot
be reused by another actor. Draft writes never inherit a missing project, date,
hours, or description from conversation history.

The planner represents follow-ups with `conversation_relation` and
`inherit_fields`. The server resolves only allowlisted read filters and records
field provenance. Draft fields are never inherited.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload --port 8000
```

The Demo Core API must be available at `DEMO_CORE_API_BASE_URL`, which defaults
to `http://localhost:8001`.

OpenAPI documentation is available at `http://localhost:8000/docs`.

## Chat request

```bash
curl http://localhost:8000/chat \
  -H 'X-Actor-ID: 3' \
  -H 'Content-Type: application/json' \
  -d '{"message":"How many hours did I log on Apollo this week?"}'
```

Responses include a human-readable message and structured `tool_events`. Chart
requests include chart-ready `data`. Complete draft requests include a
`confirmation` card containing the Core API token and preview; the web client
must require an explicit user action before calling Core API confirmation.

Policy answers include a `citations` array with the authored source ID, title,
section, repository path, and supporting excerpt. The local retriever refuses
when its evidence score is below threshold.

## Supported local prompts

- `Who am I?`
- `Which departments can I see?`
- `List employees`
- `Which projects can I see?`
- `Who is on the Apollo project?`
- `Show my last 5 submitted time entries`
- `显示我上周的工时记录`
- `How many hours did I log on Apollo this week?`
- `Show my hours status summary`
- `Show monthly hours by project as a chart`
- `Can I approve my team's pending time entries?`
- `What is the weekly time submission deadline policy?`
- `工时提交截止时间是什么？`
- `Draft 2.5 hours on Apollo for 2026-07-29: Reviewed export behavior`

Multi-turn examples:

```text
How many hours did I log on Apollo this week?
What about Beacon?
Only show submitted entries.
```

Read queries understand explicit dates plus today, yesterday, this/last week,
this/last month, and the last N days. Results always remain inside the Core
API's actor scope.

## Operations

- `/health` reports process health and planner mode.
- `/ready` checks Core API connectivity and reports loaded policy chunks.
- `/observability` returns a JSON snapshot of request and intent counters.
- `/metrics` exports the same low-cardinality counters in Prometheus format.
- Valid `X-Request-ID` values are echoed; otherwise the API generates one.

No prompt, answer, actor ID, or workforce record is written to operational
logs.

## Tests

```bash
pytest
```
