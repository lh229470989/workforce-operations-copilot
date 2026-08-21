# AcmeWorks Demo Core API

This service is a self-contained FastAPI workforce system using only fictional
AcmeWorks people, projects, and activity. It has no production adapters or
external dependencies.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn app.main:app --reload --port 8001
```

The SQLite database is created at `./data/demo.db` and seeded automatically on
first startup. Seed time entries are positioned relative to the startup week so
prompts such as "this week" remain useful. Set `DEMO_DATABASE_URL` to use
another SQLite location. OpenAPI documentation is available at
`http://localhost:8001/docs`, with the raw schema at `/openapi.json`.

## Demo identities and authorization

Pass one of these IDs in the `X-Actor-ID` header. The server loads the role from
SQLite; callers cannot supply or override a role.

| ID | Persona | Role | Scope |
| --- | --- | --- | --- |
| 3 | Jamie Rivera | employee | Self |
| 2 | Morgan Lee | manager | Self and direct reports |
| 1 | Avery Chen | admin | All fictional records |

Employees can draft only their own time. Managers can approve submitted time
for direct reports but cannot self-approve. Admins have global read scope and
may draft for any project member or decide any other employee's submitted time.

## API surface

All endpoints except `/health` require `X-Actor-ID`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/me` | Current demo persona |
| GET | `/departments` | Visible departments |
| GET | `/employees`, `/employees/{id}` | Role-scoped employees |
| GET | `/projects`, `/projects/{id}` | Role-scoped projects |
| GET | `/projects/{id}/members` | Visible project members |
| GET | `/time-entries`, `/time-entries/{id}` | Filterable, scoped time |
| GET | `/time-entry-suggestions` | Personal suggestions from recent work |
| GET | `/approvals` | Approval history in scope |
| GET | `/reports/weekly` | Role-scoped weekly report |
| GET | `/reports/weekly.csv` | Download the same report as CSV |
| POST | `/analytics/query` | Compile a declarative, role-scoped read query |
| GET | `/stats/summary` | Hours by status |
| GET | `/stats/hours-by-project` | Project totals and date filters |
| GET | `/stats/monthly-hours` | Monthly totals |
| POST | `/time-entries/dry-run` | Preview a time-entry draft |
| POST | `/time-entries/batch/dry-run` | Preview up to 10 time-entry drafts |
| POST | `/time-entries/{id}/approval/dry-run` | Preview approval/rejection |
| POST | `/actions/{token}/confirm` | Explicitly confirm a preview |
| POST | `/api/v1/integrations/work-events:ingest` | Signed WorkEvent ingestion; creates a suggestion only |
| GET | `/integration-suggestions` | List the current actor's reviewable external suggestions |
| POST | `/integration-suggestions/{id}/prepare` | Revalidate and create an actor-bound dry-run |
| GET | `/integration-notifications/preview` | Actor-scoped simulated notification evidence |
| POST | `/api/v1/integrations/notifications/{event_id}:claim` | Signed, atomic notification delivery claim |
| POST | `/api/v1/integrations/notifications/{event_id}:complete` | Signed terminal delivery result callback |

### Two-step write example

```bash
curl -s http://localhost:8001/time-entries/dry-run \
  -H 'X-Actor-ID: 3' \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": 1,
    "work_date": "2026-07-23",
    "hours": 2.5,
    "description": "Reviewed export behavior"
  }'
```

Copy the returned `confirmation_token`, inspect the preview, then confirm:

```bash
curl -s http://localhost:8001/actions/TOKEN/confirm \
  -H 'X-Actor-ID: 3' \
  -H 'Content-Type: application/json' \
  -d '{"confirm": true}'
```

Tokens expire after 15 minutes, are bound to the actor that created them, and
can be used only once. Confirmation creates an audit event. Approval decisions
also create an approval record.

The suggestion endpoint is read-only and derives candidates only from the
actor's own recent fictional entries and current project memberships. A batch
dry-run validates every item before issuing one confirmation token. Confirmation
rechecks authorization and creates all entries in one transaction, so a failed
item cannot leave a partially written batch.

The lifecycle API also supports dry-run update, delete, submit, withdraw, and
atomic batch approval. `GET /reports/time-entries.csv` reuses the list filters
and role scope. `/audit-events` and `/audit-events/stats` are admin-only and
omit payload details by default.

## Signed integration ingest

The WorkEvent endpoint is disabled unless `COPILOT_INGEST_HMAC_SECRET` is set at
runtime. It validates the exact raw body signature, a ±300 second timestamp,
a one-use nonce, the versioned WorkEvent contract, source/person/project
mappings, membership, date window and revision idempotency key. A valid request
creates or updates `IntegrationSuggestion`; it never creates a `PendingAction`,
confirmation token or time entry.

Source account and Calendar identifiers are stored only as SHA-256 hashes.
Runtime secrets are never stored in SQLite. The optional
`COPILOT_INGEST_HMAC_SECRET_NEXT` supports a bounded key-rotation window. Public
CI uses fictional fixed keys and fixtures only.

The review endpoint only returns suggestions owned by the current actor. The
prepare step accepts bounded editable business fields and rechecks membership,
duplicate and daily-hours rules. Confirmation rechecks the current revision and
atomically creates the time entry plus its unique source link, so a modified or
already-confirmed Calendar source cannot create a second record.

Integration confirmation also writes a minimal `time_entry.confirmed` outbox
event in the same transaction. The event omits descriptions, Calendar IDs,
emails, actor IDs and confirmation tokens. Notification claim/complete calls
require the separate runtime-only `COPILOT_NOTIFICATION_CALLBACK_HMAC_SECRET`;
they never reuse the ingest key. A delivery result of `delivery_unknown` is
terminal and cannot be claimed again automatically. The public UI reads only
an actor-scoped simulated preview and never calls Slack.

## Tests

```bash
pytest
```
