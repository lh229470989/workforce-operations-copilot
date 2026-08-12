# AcmeWorks MCP Server

This standalone service exposes the fictional AcmeWorks demo through MCP 2.0
Streamable HTTP at `http://localhost:8002/mcp`. Its tools call the Core API;
they never import the Core database models or open SQLite.

## Capability surface

- Scoped identity, department, employee, project, membership, time-entry,
  approval-queue, summary, and declarative analytics reads.
- Time-entry and approval dry-runs. The confirmation token is returned only in
  MCP result `_meta` for a trusted host UI; it is excluded from model-visible
  text and structured content. There is intentionally no confirmation tool.
- Capability and actor-scope resources, plus weekly-report, approval-review,
  draft-preparation, and comparison prompts.

This public demo accepts an explicit seeded `actor_id` on every tool. A real
deployment must replace persona selection with OAuth and map the authenticated
principal server-side; never let a production model choose arbitrary identities.

## Inspect locally

Start Docker Compose, then connect an MCP Inspector/client to
`http://localhost:8002/mcp` using Streamable HTTP. Health is at `/health`.

```bash
cd services/acmeworks-mcp
python -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```
