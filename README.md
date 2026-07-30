# Workforce Operations Copilot

A secure, self-hosted demo of an AI copilot for internal operations. It answers policy questions, retrieves workforce data, drafts time entries, and performs role-aware actions with an explicit approval step.

## Status

The first full-stack demo milestone is implemented:

- `services/demo-core-api` provides the synthetic workforce system.
- `services/ai-api` provides role-aware LangGraph orchestration with read-only
  tools and dry-run-only time drafting.
- `apps/web` provides the chat workspace, tool-event cards, charts, demo-role
  switching, and an explicit confirmation card.
- `knowledge-base` contains original fictional policies used by a local
  evidence-threshold retriever with structured citations.
- Release assurance includes an authored evaluation set, request metrics,
  security headers, a publication scan, and CI verification.

Start the implemented service with:

```bash
docker compose up --build
```

Then open `http://localhost:3000` for the demo workspace,
`http://localhost:8000/docs` for the AI API, or `http://localhost:8001/docs`
for the Core API. See
[`services/demo-core-api/README.md`](services/demo-core-api/README.md) for demo
personas and write-confirmation examples, and
[`services/ai-api/README.md`](services/ai-api/README.md) for chat tools and
model configuration. Web verification steps are in
[`apps/web/README.md`](apps/web/README.md).

## Planned demo

- Ask policy questions with cited knowledge-base sources.
- Query synthetic projects and time entries in natural language.
- Draft a time entry, inspect a dry-run preview, then explicitly approve it.
- Compare monthly project hours with a chart.
- Demonstrate role-aware access for employee, manager, and admin personas.

## Architecture

```text
Next.js web app → FastAPI AI API → tools / RAG / policy checks → Demo Core API + SQLite
```

The Next.js app proxies requests server-side to the LangGraph-based AI API and
the synthetic workforce Core API so the browser never becomes the
authorization boundary.

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
cd apps/web && npm test && npm run typecheck && npm run build

docker compose up --build -d
docker compose ps
```

Operational endpoints are available at `http://localhost:8000/health`,
`/ready`, `/observability`, and `/metrics`. Request telemetry contains route,
status, latency, request ID, and planned intent only; it does not record chat
messages or actor attributes.

Release controls are documented in [SECURITY.md](SECURITY.md) and
[docs/release-checklist.md](docs/release-checklist.md).
