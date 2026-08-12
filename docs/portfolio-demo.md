# Portfolio demo package

This package is designed for an Upwork portfolio item, proposal attachment, or
short screen recording. It uses only the fictional AcmeWorks dataset.

## 60–90 second walkthrough script

Target length: about 75 seconds. Record at `1280 × 720`, keep the browser zoom
at 100%, and do not show `.env`, terminal history, browser extensions, or real
accounts.

| Time | Screen action | Narration |
| --- | --- | --- |
| 0–8s | Open the welcome screen and point to the three demo identities. | “This is a review-first AI operations copilot for small teams. It turns natural-language requests into role-scoped, inspectable workflows.” |
| 8–24s | As Jamie, run the weekly submission-deadline policy prompt. Pause on the answer and source cards. | “Policy answers are grounded in a fictional knowledge base and show the exact supporting sections, rather than asking the viewer to trust model text.” |
| 24–39s | Return to the welcome screen and run the team-approval prompt as Jamie. Pause on the refusal and scoped time entries. | “The employee cannot perform a manager-only approval. Authorization is enforced by the API, but the assistant still returns useful information inside Jamie’s scope.” |
| 39–60s | Draft `1 hour on Apollo for 2026-12-18, description: portfolio demo`. Pause on the dry-run card. | “Writes start as a dry-run with validated fields and an expiring, actor-bound token. At this point nothing has changed.” |
| 60–70s | Click **Confirm & create** and show the success message. | “The separate confirmation request rechecks authorization and business rules, writes once, and records an audit event.” |
| 70–78s | Briefly show the chart or tool-event cards. | “The same project also includes structured analytics, observable tool calls, automated tests, Docker deployment, and MCP integration.” |

If the model response is slow or materially different from the shot list, use
the local fallback for a reproducible take. Do not splice in a result that the
current repository cannot reproduce.

## Screenshot set

1. [Desktop welcome and guided prompts](assets/portfolio/01-desktop-welcome.jpg)
2. [Grounded policy answer](assets/portfolio/02-grounded-policy.jpg)
3. [Role-aware refusal](assets/portfolio/03-role-refusal.jpg)
4. [Dry-run and explicit confirmation](assets/portfolio/04-dry-run-confirmation.jpg)
5. [Role-scoped chart](assets/portfolio/05-role-scoped-chart.jpg)
6. [Mobile welcome](assets/portfolio/06-mobile-welcome.jpg)

Before publishing, rerun the workflows and replace any screenshot that no
longer matches the current UI. Review every image at full size for secrets,
account information, notifications, or unrelated browser content.

## Upwork portfolio copy

### Title

Review-First AI Operations Copilot — FastAPI, Next.js, LangGraph, and MCP

### Short description

I designed and built a secure AI workflow demo for small and growing teams.
Users can ask workforce-policy and reporting questions in natural language,
inspect role-scoped data and tool activity, and prepare business writes through
a dry-run plus explicit confirmation flow. The solution includes a Next.js
workspace, FastAPI services, LangGraph orchestration, grounded retrieval, an
MCP server, Docker Compose, automated evaluations, browser tests, and CI.

### Problem

Internal operations requests often arrive as informal chat, while the resulting
access decisions and record changes must remain predictable and auditable.
Typical AI demos hide this gap by letting the model act as if it were the
authorization layer.

### Solution

I separated language understanding from trusted execution. The assistant can
plan reads and propose changes, but the Core API enforces identity scope,
business rules, idempotent confirmation tokens, and audit records. Grounded
answers show their fictional policy sources, and the UI renders business
actions as trusted structured components rather than model-generated links.

### Result

The finished standalone demo provides three clear sales paths—grounded policy
Q&A, permission refusal, and review-first writes—and can be run locally as a
four-service Docker Compose stack. Its delivery evidence includes 120 authored
Agent/RAG/security benchmark cases, service and UI tests, browser E2E checks,
dependency audit, container builds, and a publication security scan. No client
or employer data is used.

## Publication checklist

- Record a fresh take from a clean synthetic database.
- Confirm the policy, refusal, dry-run, confirmation, and audit paths still work.
- Remove notifications, account avatars, extensions, and unrelated tabs.
- Run `python3 scripts/security_scan.py` and the full verification suite.
- Upload the video to the selected portfolio host before adding its URL to the README.
- Add a homepage URL only after the hosted demo has monitoring, budget limits,
  abuse controls, and a tested shutdown path.
