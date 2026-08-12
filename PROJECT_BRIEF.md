# Project Brief

## Goal

Create a public, portfolio-ready demonstration of a secure enterprise AI copilot. The demo must be self-contained, runnable locally, and fully detached from all customer systems and data.

## Non-negotiable constraints

- Do not copy code or documents until ownership and publication rights are confirmed.
- Never copy production URLs, IP addresses, credentials, tokens, account data, policies, screenshots, or Git history.
- Use fictional company, users, projects, policies, and metrics.
- Keep every data-changing action behind a dry-run and explicit confirmation.

## First delivery milestone

1. `demo-core-api`: FastAPI + SQLite with synthetic employees, projects, and time entries.
2. `ai-api`: one chat endpoint with read-only tools and a draft-only time-entry tool.
3. `web`: chat workspace with tool-event cards and a confirmation card.
4. Docker Compose starts the full demo with one command.

## Initial demo prompts

- "How many hours did I log on Apollo this week?"
- "Draft my remaining time entries for this week based on recent work."
- "Show monthly hours by project as a chart."
- "Can I approve my team's pending time entries?"

## Completed expansion sequence

The original demo was expanded in this order, with each capability authored
from scratch for AcmeWorks:

1. Smart recent-work suggestions and atomic batch time-entry drafts.
2. Conversational approval/rejection dry-runs with separate confirmation.
3. SSE answers with live planner and tool status.
4. Role-scoped weekly reports and CSV export.
5. Validated multi-tool comparison plans.
6. Versioned, checksummed planner and composer prompt files.
7. Actor-bound persistent sessions and privacy-controlled preferences.
8. Coverage-aware hybrid policy retrieval and declarative safe analytics.

## Completed implementation roadmap

1. **Demo Core API** — synthetic workforce records, role-scoped reads,
   dry-runs, confirmations, audit records, tests, and a container.
2. **AI API** — safe planning, read tools, and draft-only write proposals.
3. **Web workspace** — demo personas, tool events, charts, and confirmation
   cards.
4. **Query and conversation foundation** — expanded bilingual queries,
   structured conversation relations, authoritative actor context, and
   actor-bound short sessions.
5. **Suggested work and approval proposals** — personal recent-work
   suggestions, atomic batch time-entry dry-runs, and conversational approval
   or rejection dry-runs for exact entries.
6. **Grounded policy knowledge** — original AcmeWorks policies, progressive
   retrieval, evidence thresholds, refusal, and structured citations.
7. **Release assurance** — authored evaluations, privacy-conscious
   observability, security headers and scans, CI, threat documentation, and a
   public-release checklist.
8. **Advanced retrieval and analytics** — compound-query evidence coverage,
   bounded declarative analytics, Core-enforced row visibility, SQLite
   query-only execution, and a one-second execution budget.

Milestones 1–8 are implemented. Every write-capable conversation remains a
proposal until the user separately confirms a server-authorized token.

The next portfolio and market-positioning phases are tracked in
[`docs/portfolio-roadmap.md`](docs/portfolio-roadmap.md). They focus on SMB AI
automation, presentation quality, one real integration case, and evidence-led
specialization rather than adding more unvalidated Agent features.
