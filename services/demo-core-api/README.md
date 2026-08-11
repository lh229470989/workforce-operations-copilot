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

## Tests

```bash
pytest
```
