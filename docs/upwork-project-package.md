# Upwork SMB AI Automation project package

Status: **repository package ready; private integration proof and Upwork account
submission remain manual**

Updated: 2026-08-21

This file is the paste-ready sales package for one focused Upwork Project Catalog
offer. It does not claim that the public demo connects to real Google or Slack.
The offer is a client service; AcmeWorks is the fictional proof project.

## 1. Recommended positioning

Profile headline:

> AI Automation Engineer | n8n, APIs, Approval Workflows, FastAPI

One-line value proposition:

> I build reliable SMB automations that connect business tools, validate data,
> require human approval for sensitive writes, and ship with tests and handoff
> documentation.

Do not lead with LangGraph, MCP, RAG, or framework names. Lead with the business
workflow, reliability, approval boundary, and handoff. Use the deeper Agent stack
as evidence when a client actually needs it.

## 2. Project Catalog listing

### Title

> I will build a secure n8n AI automation for your SMB workflow

Upwork advises using a short offer-focused title, putting discovery keywords in
search tags, and not repeating “You will get” in the title. It currently permits
up to three packages and five search tags. See the official
[Project Catalog creation guide](https://support.upwork.com/hc/en-us/articles/360057397533-How-to-create-a-project-in-Project-Catalog).

Suggested category: choose the closest available option under **Development &
IT** for automation or integrations; do not choose “Other” unless no relevant
category exists.

Search tags:

1. `n8n`
2. `Workflow Automation`
3. `AI Automation`
4. `API Integration`
5. `Webhook`

### Paste-ready project summary

> Manual handoffs, copied data, and unreviewed AI actions make small-business
> workflows slow and risky. I will design and build a bounded automation that
> connects your selected tools, transforms data into a clear schema, handles
> duplicates and temporary failures, and keeps sensitive writes behind an
> explicit approval step.
>
> Your delivery can include importable n8n workflows, API or webhook adapters,
> a lightweight approval interface, idempotency and retry rules, mock-based
> tests, deployment configuration, and a concise operations runbook. Credentials
> stay outside source control and public workflow exports.
>
> My reference implementation demonstrates a Calendar-style event becoming a
> reviewable work suggestion, a server-authorized confirmation, and a trusted
> notification event. Its public path is clearly simulated; real services are
> tested only with isolated client-approved test accounts.
>
> This project is best for one well-defined SMB workflow. Multi-tenant SaaS,
> enterprise SSO, broad data migration, and open-ended agent development require
> a custom contract.

### Packages

Prices below are launch hypotheses, not claims about guaranteed market rates.
Review them after the first 10–20 qualified proposals or three client calls.

| Package | Suggested price | Delivery | Revisions | Included scope |
| --- | ---: | ---: | ---: | --- |
| Starter — Automation Blueprint | USD 350 | 3 days | 1 | One workflow design, bounded input/output schema, error and credential plan, importable mock workflow, implementation estimate |
| Standard — Working Integration | USD 900 | 7 days | 2 | One trigger and one destination, up to two n8n workflows, mapping, approval gate, retries, idempotency, mock tests, setup guide |
| Advanced — Secure Handoff | USD 1,800 | 14 days | 2 | Standard plus custom API/webhook adapter, signed requests, persistent audit/delivery state, deployment config, failure drill and handoff session |

Scope limits for every tier:

- one business process and one client organization;
- fictional or client-approved test data during development;
- no production data migration;
- no unrestricted model access to raw third-party payloads;
- no multi-tenant OAuth installation flow unless separately quoted;
- third-party subscription, hosting, model, and usage fees are not included.

Recommended add-ons:

- additional source or destination adapter: USD 300–600;
- second approval role or branch: USD 250;
- deployment to an existing client environment: USD 300;
- 14-day post-delivery monitoring: USD 250;
- expedited delivery: price only after confirming access and test-account readiness.

### Client requirements

Mark the first six as mandatory. Do not ask the client to paste passwords, OAuth
tokens, webhook URLs, personal contact information, or payment information into
the Project Catalog requirements form.

1. Describe the current process, trigger, desired result, and measurable pain in
   five to ten sentences.
2. Name the one source system and one destination system in scope.
3. Provide two to five sanitized example inputs and the expected output for each.
4. Identify which action, if any, requires human approval and who owns that
   decision by role.
5. State the target runtime: existing self-hosted n8n, a client-managed server,
   or design/template delivery only.
6. Confirm that isolated test accounts/workspaces and synthetic data can be used.
7. Optional: provide current workflow diagrams, API documentation, error samples,
   and non-sensitive volume/latency expectations.

Upwork starts the delivery clock only after mandatory requirements are submitted;
its current standard-project deadline for those requirements is 48 hours. See
[project requirements guidance](https://support.upwork.com/hc/en-us/articles/4407894806547-How-to-set-and-manage-project-requirements).

### Project steps

1. Confirm the workflow boundary, success metric, systems, and test data.
2. Freeze schemas, authentication, approval, idempotency, retry, and failure rules.
3. Build the automation and adapters against mocks or isolated test accounts.
4. Demonstrate happy path, duplicate input, invalid payload, and temporary failure.
5. Deliver sanitized exports, tests, setup guide, recovery runbook, and handoff.

Do not add “client submits requirements” or “client approves delivery” as project
steps; Upwork already provides those lifecycle steps.

### FAQs

**Will you connect my production accounts immediately?**

No. I start with sanitized fixtures or isolated test accounts. Production access
is introduced only after the data contract, permissions, failure behavior, and
rollback path are reviewed.

**Can AI write directly to my CRM, calendar, or database?**

Not by default. Sensitive writes receive a structured preview and explicit human
confirmation, followed by server-side permission and business-rule checks.

**Do you host n8n for me?**

The base packages deliver importable workflows and configuration guidance. I can
deploy to a client-owned environment as an add-on. I do not provide a shared
public n8n instance.

**Will credentials appear in the workflow export or repository?**

No. Secrets stay in the target platform's credential store, runtime environment,
or approved secret manager. Public exports, logs, tests, screenshots, and CI use
placeholders and fictional data.

**What happens when an API times out or sends the same event twice?**

The agreed design defines bounded retries, idempotency keys, and explicit unknown
delivery states. Ambiguous notification delivery is not blindly repeated.

**Is this a full SaaS product or an open-ended AI agent?**

No. The catalog offer is one bounded automation. Multi-tenant identity, billing,
large migrations, broad RAG systems, or an open-ended agent should be scoped as a
separate milestone contract.

## 3. Portfolio item copy

Title:

> Review-first Workforce Operations Copilot and SMB Automation

Role:

> Product architecture, AI workflow, FastAPI and Next.js implementation, n8n
> integration design, security boundaries, tests, CI, Docker, and documentation.

Short description:

> Built a synthetic workforce operations system that converts natural-language
> requests and Calendar-style events into role-scoped reads or reviewable write
> proposals. Sensitive changes require a dry-run, actor-bound confirmation, and
> server-side re-authorization. A simulated Calendar-to-notification path proves
> the full lifecycle without public credentials, while two import-validated n8n
> templates document the private Google Calendar read-only and Slack Incoming
> Webhook adapters. Duplicate sources cannot create duplicate time entries, and
> CI verifies contracts, security scans, containers, and browser behavior.

Results/evidence bullets:

- full browser path from fictional external event to confirmed notification;
- signed 16 KiB WorkEvent contract with replay protection and revision idempotency;
- persistent source link, outbox, and claim-before-notification delivery ledger;
- two credential-free workflows imported successfully into n8n `2.34.6`;
- 8 CI jobs passing on the latest merged implementation PR;
- synthetic data only; no employer, client, Google, or Slack credentials exposed.

Repository: use the GitHub repository link in the Upwork portfolio link field if
allowed. Do not place contact information or off-platform payment language in the
description or gallery.

## 4. Proposal opener variants

### n8n integration job

> Your workflow needs more than connected nodes: the duplicate, retry, credential,
> and approval behavior must be explicit. I recently built a review-first SMB
> automation reference with two importable n8n workflows, signed webhooks,
> persistent idempotency, mock tests, and a handoff runbook. For your project I
> would first freeze the source/destination contract and failure cases, then build
> one vertical path against sanitized fixtures before touching production access.

### AI agent with business writes

> The critical boundary in your brief is the write step. I would keep model output
> as a proposal, issue a short-lived actor-bound confirmation, and recheck
> permissions and business rules server-side before execution. My reference
> implementation demonstrates this pattern end to end with FastAPI, Next.js,
> LangGraph, audit metadata, contract tests, and browser E2E.

### API/webhook reliability job

> I can implement this as a bounded API integration with exact schemas, raw-body
> HMAC verification, timestamp/replay protection, deterministic idempotency, and
> limited Retry-After-aware retries. I would include mock-server tests for success,
> deterministic 4xx, rate limits, timeouts, and ambiguous delivery—not just the
> happy path.

## 5. Upwork gallery and 60-second video

Current Upwork guidance allows up to 20 images, requires JPEG/PNG under 10 MB,
recommends 4:3 and sharp display at `1000 × 750`, and permits one MP4 video up to
60 seconds and 100 MB. Gallery assets must avoid contact information, watermarks,
unauthorized logos, clickbait, poor crops, and text-heavy layouts. See
[image and video requirements](https://support.upwork.com/hc/en-us/articles/1500011309082-How-to-add-images-and-video-to-your-Project-Catalog-project).

Recommended gallery order after preparing compliant 4:3 exports:

1. clean product overview with the “Ask. Inspect. Confirm.” value statement;
2. structured grounded answer and fictional source evidence;
3. permission refusal;
4. dry-run plus explicit confirmation;
5. simulated integration review and notification evidence;
6. small architecture/security visual without third-party logos.

The existing 80-second WebM GitHub walkthrough is useful repository evidence but
does **not** meet the current Project Catalog video requirements. Record a separate
MP4 no longer than 60 seconds.

### 55-second script

| Time | Visual | English narration |
| --- | --- | --- |
| 0–6s | Welcome and roles | “I build review-first AI automation for small and growing teams.” |
| 6–15s | Grounded policy answer | “Natural-language requests become grounded, role-scoped results—not unchecked model text.” |
| 15–25s | Employee refusal | “Server-side permissions block actions the current user cannot perform.” |
| 25–38s | Calendar suggestion and dry-run | “External events create bounded suggestions only. A human reviews the exact proposed write.” |
| 38–47s | Explicit confirmation | “Confirmation is actor-bound, short-lived, and re-authorized before the database changes.” |
| 47–55s | Simulated notification and CI | “Only confirmed results reach notification, with idempotency, tests, sanitized templates, and handoff documentation.” |

Do not show Google, Slack, n8n, Upwork, or other third-party logos in the gallery
video; show the owned UI and describe adapters in text. Do not show browser account
chrome, webhook URLs, OAuth screens, logs, credentials, or personal contact data.

## 6. Readiness and remaining gap

| Item | Status | Evidence or next action |
| --- | --- | --- |
| Clear SMB automation positioning | Ready | README and this paste-ready package |
| Public no-credential demo path | Ready locally | Calendar fixture → dry-run → confirm → simulated notification E2E |
| Reusable n8n deliverable | Ready | two sanitized JSON exports, scanner, n8n `2.34.6` import proof |
| Security/reliability proof | Ready | HMAC, nonce, idempotency, unique source link, outbox and delivery claim tests |
| CI/repository proof | Ready | latest implementation PRs merged with 8/8 checks |
| Failure recovery and handoff | Ready | `integrations/n8n/README.md` and design document |
| Project Catalog copy and tiers | Ready as draft | paste from this file; adjust category/price in the account UI |
| 4:3 Upwork gallery exports | Manual | create owned `1000 × 750` JPEG/PNG variants and upload in final order |
| Upwork-specific video | Manual | record 55-second English MP4, under 100 MB |
| Private Google/n8n/Slack execution | Manual and credential-dependent | isolated accounts, exact read-only scope, fictional event, dedicated Slack channel |
| Private evidence statement | Blocked until verified | only after real run may README say “verified in private test environment” |
| Hosted public URL | Optional, not required | keep absent unless abuse controls and operating budget are approved |
| Listing submission | Manual account action | choose final prices/concurrency and submit from the user's Upwork account |

Repository work is therefore complete enough to publish a truthful Project
Catalog draft and use the project in proposals. The critical remaining proof is
one private real-account run and one compliant 55-second MP4; neither should be
simulated or claimed prematurely.

## 7. Private evidence checklist

Before recording:

- set `COPILOT_PUBLIC_MOCK_ENABLED=false`;
- use the isolated Google test account, test-only Cloud project, consent config,
  dedicated fictional Calendar, exact `calendar.readonly` scope, and low quota;
- use Slack Developer Sandbox or an isolated free workspace and dedicated channel;
- bind runtime secrets without exporting resolved values;
- import both templates into clean n8n `2.34.6` and confirm they remain disabled;
- run fixed HMAC vectors, duplicate fixture, invalid mapping, 429, and timeout tests;
- clear notifications, avatars, unrelated tabs, logs, and browser account details.

After recording:

- delete fictional events and test-channel messages;
- revoke temporary OAuth tokens and rotate the Slack webhook/HMAC secrets;
- inspect the final MP4 frame by frame for URLs, credentials, account identity, and
  third-party logos;
- update the README evidence sentence and roadmap only after the real run passes;
- upload the final assets through the Upwork account and submit for review.
