# Workforce Operations Copilot

A secure, self-hosted demo of an AI copilot for internal operations. It answers policy questions, retrieves workforce data, drafts time entries, and performs role-aware actions with an explicit approval step.

## Status

The portfolio demo is implemented and runs as a four-service Docker Compose
stack:

- `services/demo-core-api` provides the synthetic workforce system.
- `services/ai-api` provides LLM-first, role-aware LangGraph orchestration with
  grounded answer generation, read-only tools, and dry-run-only single or
  batch time drafting.
- `apps/web` provides the chat workspace, tool-event cards, charts, demo-role
  switching, live SSE agent status, and an explicit confirmation card.
- `services/acmeworks-mcp` exposes scoped reads, resources, prompts, and
  preview-only writes over MCP 2.0 Streamable HTTP.
- `knowledge-base` contains original fictional policies used by a local
  evidence-threshold retriever with structured citations.
- Release assurance includes 120 authored Agent/RAG/security benchmark cases,
  metadata-only Agent audit, request metrics, security headers, publication
  scans, and Playwright browser E2E in CI.

Start the implemented service with:

```bash
docker compose up --build
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` to run the real LLM
agent. With no key, the same stack remains available as an explicitly labeled
`local fallback`; it does not pretend that deterministic routing is a model.

Then open `http://localhost:3000` for the demo workspace,
`http://localhost:8000/docs` for the AI API, or `http://localhost:8001/docs`
for the Core API. MCP clients connect to `http://localhost:8002/mcp`. See
[`services/demo-core-api/README.md`](services/demo-core-api/README.md) for demo
personas and write-confirmation examples, and
[`services/ai-api/README.md`](services/ai-api/README.md) for chat tools and
model configuration. Web verification steps are in
[`apps/web/README.md`](apps/web/README.md).

## Implemented demo

- Ask policy questions with cited knowledge-base sources.
- Query synthetic projects and time entries in natural language.
- Review personal time-entry suggestions derived from recent fictional work.
- Draft a time entry, inspect a dry-run preview, then explicitly approve it.
- Draft up to 10 time entries as one atomic dry-run and confirmation.
- Edit, delete, submit, or withdraw an exact entry through the same two-step boundary.
- Let an authorized manager propose approval or rejection for an exact entry,
  then confirm it through the same separate write boundary.
- Batch-decide up to 20 submitted entries after atomic scope validation.
- Compare monthly project hours with a chart.
- Compare 2–4 authorized project or date slices through a validated multi-tool plan.
- Ask compound policy questions with hybrid retrieval and evidence coverage.
- Run declarative analytics through a role-scoped, query-only SQL compiler.
- Demonstrate role-aware access for employee, manager, and admin personas.
- Stream model text deltas, export scoped time slices, inspect admin audit
  metadata, hot-reload policies, and keep user-controlled structured preferences.
- Validate duplicate and cumulative daily hours at preview and confirmation.
- Manage explicit, non-sensitive structured memories through actor-bound
  dry-run and confirmation.
- Render role-scoped time entries and report downloads as trusted structured
  UI instead of model-authored Markdown or links.
- Render employees, projects, project members, approval queues, and explicit
  memories as structured cards/tables; export scoped XLSX and printable PDF.
- Use natural-language memory commands with the same dry-run and explicit
  confirmation boundary as workforce writes.

## Architecture

```text
Next.js web app → FastAPI AI API → tools / RAG / policy checks → Demo Core API + SQLite
MCP client → AcmeWorks MCP (preview-only writes) ──────────────┘
```

The Next.js app proxies requests server-side to the LangGraph-based AI API and
the synthetic workforce Core API so the browser never becomes the
authorization boundary.

架构说明从 [`docs/README.md`](docs/README.md) 开始，包含：

- [`系统架构总览`](docs/system-overview.md)
- [`Agent 运行时与 LLM 调用链`](docs/agent-runtime.md)
- [`权限、安全与上下文管理`](docs/security-and-context.md)
- [`本地运行与调试`](docs/local-development.md)

## Safety boundary

This is a fresh showcase project, not a public copy of an internal system. Use only fictional data and a new Git history. Before publishing, run a secret scan and manually review all docs, screenshots, and commit history.

## Development plan

See [PROJECT_BRIEF.md](PROJECT_BRIEF.md) for scope and next steps, and
[docs/architecture.md](docs/architecture.md) for target boundaries.

## Verification

```bash
python3 scripts/security_scan.py

cd services/demo-core-api && pytest
cd services/ai-api && pytest
cd services/acmeworks-mcp && pytest
cd apps/web && npm test && npm run typecheck && npm run build
cd apps/web && npm run test:e2e

docker compose up --build -d
docker compose ps
```

Operational endpoints are available at `http://localhost:8000/health`,
`/ready`, `/observability`, and `/metrics`. Request telemetry contains route,
status, latency, request ID, and planned intent only; it does not record chat
messages or actor attributes.

Release controls are documented in [SECURITY.md](SECURITY.md) and
[docs/release-checklist.md](docs/release-checklist.md).

## License

Released under the [MIT License](LICENSE). All AcmeWorks people, organizations,
projects, policies, records, and metrics are fictional and authored for this
standalone demonstration.
