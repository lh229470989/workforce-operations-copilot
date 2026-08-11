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
- Time-entry write proposals call only the Core API's single or batch dry-run
  routes.
- The AI API can create an approval/rejection dry-run for one exact entry, but
  never confirms a token.
- Missing draft fields cause a clarification response; the planner must not
  invent project, date, hours, or description.

## Modes

`AI_MODE=auto` is the default. With `OPENAI_API_KEY`, the service uses an LLM
for both structured planning and natural, grounded answer generation. The
model plans against a fixed intent schema; application code still performs
authorization, parameter resolution, tool execution, and write controls.

Without a key, `auto` clearly falls back to a deterministic English/Chinese
planner and response composer for offline demos. `AI_MODE=openai` requires the
key. The default hosted model is `gpt-5.6-terra` and can be changed with
`OPENAI_MODEL`. `OPENAI_BASE_URL` optionally selects an endpoint compatible with
the OpenAI Responses API without embedding any environment-specific URL in the
repository.

For DashScope in the China region, use
`OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1` and a
supported Qwen model such as `qwen-flash`. The adapter disables Qwen thinking
for schema-constrained planning and uses only Responses-compatible parameters.
`OPENAI_PLANNER_MODEL` and `OPENAI_COMPOSER_MODEL` can override the shared
`OPENAI_MODEL`; the local DashScope demo uses `qwen3.5-plus` for structured
planning and `qwen-flash` for grounded response wording.

The OpenAI mode uses the Responses API twice: first for schema-constrained
planning, then for a natural-language answer grounded in the authorized tool
result. Confirmation tokens are removed before model composition. Calls use
`store=false`, and model failures return the deterministic safe answer.

Planner and composer instructions live in `prompts/` rather than Python source.
`manifest.json` pins an immutable filename, semantic version, and SHA-256 for
each prompt. Startup fails on checksum drift, and `/health` plus `/ready`
report the active versions without returning prompt text. See
[`prompts/README.md`](prompts/README.md) for the reviewed upgrade workflow.

## Conversation and actor context

Each chat response returns an actor-bound `session_id`. SQLite keeps at most 10
turns for 30 minutes by default, including across ordinary container restarts.
This bounded memory supports safe read follow-ups. Configure the limits with
`SESSION_TTL_SECONDS` and `SESSION_MAX_TURNS`. Startup and periodic cleanup
physically remove expired sessions and expired preference proposals.

Every request refreshes authoritative fictional actor context from Core API: role, visible
departments, visible projects, and five recent time entries. A session cannot
be reused by another actor. Draft writes never inherit a missing project, date,
hours, or description from conversation history.

The planner represents follow-ups with `conversation_relation` and
`inherit_fields`. The server resolves only allowlisted read filters and records
field provenance. Draft fields are never inherited.

Privacy preferences are available at `GET /preferences`. Updates and complete
private-state deletion both require dry-run plus actor-bound confirmation.
Users control bounded history, `auto`/English/Chinese wording, and a currently
visible preferred project. Preferences never alter Core API authorization.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload --port 8000
```

The Demo Core API must be available at `DEMO_CORE_API_BASE_URL`, which defaults
to `http://localhost:8001`.

Relative business dates use `BUSINESS_TIMEZONE` (`Asia/Shanghai` by default)
rather than the container's UTC date. The Core API uses the same setting for
suggestions, weekly reports, and first-start seed positioning.

OpenAPI documentation is available at `http://localhost:8000/docs`.

`POST /chat/stream` accepts the same request as `/chat` and returns SSE events:
`status` for planning/executing/composing, metadata-only `tool` completions,
one full `result`, and `done`. Intermediate events never contain tool outputs
or confirmation tokens. The original `/chat` JSON contract remains available.

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
Suggestion requests return review candidates without creating a pending action.
A batch request accepts at most 10 explicit entries and returns one confirmation
card; the model cannot confirm it.
An approval action requires an exact time-entry ID and explicit approve/reject
decision. Eligibility questions only inspect the queue. Core API enforces the
manager/admin scope, submitted status, and self-approval prohibition both when
creating the preview and when confirming it.

Policy answers include a `citations` array with the authored source ID, title,
section, repository path, and supporting excerpt. The local retriever refuses
when its evidence score is below threshold.

## Supported local prompts

- `你好`
- `Hello`
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
- `Generate my weekly report for this week`
- `Compare Apollo and Beacon hours this week`
- `Compare Apollo this week and last week`
- `SQL analysis: group hours by status this week`
- `Give me time-entry suggestions for today`
- `给我一些今天的智能填报建议`
- `Can I approve my team's pending time entries?`
- `Approve time entry 2, comment: Looks complete`
- `驳回工时记录 2，备注：请补充说明`
- `What is the weekly time submission deadline policy?`
- `工时提交截止时间是什么？`
- `Draft 2.5 hours on Apollo for 2026-07-29: Reviewed export behavior`
- `批量填报：2026-08-03 Apollo 2 小时，描述：整理接口文档；2026-08-04 Apollo 3 小时，描述：补充接口测试`

Multi-turn examples:

```text
How many hours did I log on Apollo this week?
What about Beacon?
Only show submitted entries.
```

Read queries understand explicit dates plus today, yesterday, this/last week,
this/last month, and the last N days. Results always remain inside the Core
API's actor scope.

Comparison requests produce 2–4 read-only analysis slices. Application code
validates every label, project, status, and date range before the first data
query, then executes only registered role-scoped tools. A comparison plan
cannot contain a draft, approval, confirmation, arbitrary function, or SQL.

The safe SQL intent accepts only an `AnalyticsQuerySpec`; it never accepts SQL
text. Core API compiles allowlisted dimensions/metrics with SQLAlchemy, adds the
actor's row scope, caps output at 50 groups, and executes under SQLite
`query_only`. Raw SQL-shaped prompts are refused before a Core tool call.

Policy retrieval combines normalized IDF terms, heading evidence, character
similarity, and coverage-aware reranking. Compound questions must meet both a
score threshold and a 55% concept-coverage threshold. Answers remain extractive
and cite only original AcmeWorks policy sections.

## Operations

`POST /chat/stream` emits `delta` events while the configured model composes
the answer, followed by the authoritative structured `result`. Confirmation
tokens are never present in intermediate events. Admin actor `1` may inspect
and hot-reload authored policy Markdown through `GET /knowledge` and
`POST /knowledge/reload`.

Structured long-term preferences include response detail and default report
format in addition to bounded history, language, and preferred visible project.
They can shape wording and read defaults, but never authorization or write data.

- `/health` reports process health and planner mode.
- `/ready` checks Core API connectivity and reports loaded policy chunks.
- `/observability` returns a JSON snapshot of request and intent counters.
- `/metrics` exports the same low-cardinality counters in Prometheus format.
- Valid `X-Request-ID` values are echoed; otherwise the API generates one.

No prompt, answer, actor ID, or workforce record is written to operational
logs.

`AI_STATE_DATABASE_PATH` selects the SQLite file used for bounded turns and
minimal preferences. Docker Compose stores it in a dedicated volume; users can
delete their state through the same two-step safety boundary.

## Tests

```bash
pytest
```
