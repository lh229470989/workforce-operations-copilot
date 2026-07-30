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

## Current follow-up milestone

Expand the original demo with an authored-from-scratch query foundation:

1. Register role-scoped read capabilities outside the orchestration graph.
2. Support profile, department, employee, project-member, time-entry, and
   workflow-summary queries.
3. Add English/Chinese relative-date and status filtering.
4. Add short conversation context only after the stateless query contract is
   covered by regression tests.

## Portfolio roadmap

1. **Demo Core API** — synthetic workforce records, role-scoped reads,
   dry-runs, confirmations, audit records, tests, and a container.
2. **AI API** — safe planning, read tools, and draft-only write proposals.
3. **Web workspace** — demo personas, tool events, charts, and confirmation
   cards.
4. **Query and conversation foundation** — expanded bilingual queries,
   structured conversation relations, authoritative actor context, and
   actor-bound short sessions.
5. **Suggested work and approval proposals** — batch suggestions and approval
   dry-runs. This remains a future milestone.
6. **Grounded policy knowledge** — original AcmeWorks policies, progressive
   retrieval, evidence thresholds, refusal, and structured citations.
7. **Release assurance** — authored evaluations, privacy-conscious
   observability, security headers and scans, CI, threat documentation, and a
   public-release checklist.

Milestones 1–4, 6, and 7 are implemented. Milestone 5 is intentionally not
implied by the policy or release work and remains separately scoped.
