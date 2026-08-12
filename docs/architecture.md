# Target Architecture

For a guided Chinese explanation of the implemented system, start with the
[architecture documentation index](README.md). This file remains the compact
boundary specification.

## Components

| Component | Responsibility | Public-demo constraint |
| --- | --- | --- |
| `apps/web` | Chat, data workspace, approval cards, charts | Only synthetic data |
| `services/ai-api` | Agent orchestration, RAG, authorization, tool dispatch | No production adapters |
| `services/demo-core-api` | Mock internal workforce API | SQLite and seeded fictional data |
| `services/acmeworks-mcp` | MCP 2.0 tools, resources, and prompts | Core API only; no direct DB or confirmation tool |
| `knowledge-base` | Fictional policies used for retrieval | Authored from scratch |

## Web request boundary

The Next.js application uses server-side route handlers for chat and explicit
confirmation. The browser selects only one of the three known demo personas.
Route handlers forward that actor ID, while the Core API loads the actor and
role from SQLite and applies record-level authorization.

## Context layers

1. **Authoritative actor context** is refreshed from Core API for every chat:
   role, visible departments/projects, and recent fictional time entries.
2. **Short conversation context** is SQLite-backed, actor-bound, capped at 10
   turns, and expires after 30 minutes by default.
3. **Persistent preferences** are limited to history enablement, response
   language, a currently visible preferred project, response detail, and
   default report format. Updates and deletion use dry-run plus explicit
   confirmation. They never grant access or complete write fields.
4. **Structured long-term memories** contain only explicit work, reporting,
   or collaboration preferences up to 200 characters. Every create, update,
   and delete is actor-bound and requires dry-run plus confirmation. Prompts,
   inferred traits, sensitive personal data, and authorization claims are not
   accepted as memory categories.

Conversation context may fill omitted filters for read-only follow-ups. It
never fills missing fields for a single/batch draft, approval decision, or
confirmation.

## LLM orchestration boundary

The primary configured path uses an LLM twice: schema-constrained intent
planning before tool execution, then natural-language composition after the
server has returned an authorized result. The model never executes arbitrary
code or talks directly to SQLite or the Core API.

```text
message -> LLM plan -> server validation -> allowlisted tool
        -> authorized result -> LLM answer -> structured web response
```

When no model credential is configured, the service uses a clearly labeled
local fallback. That path exists for offline availability and regression tests;
it is not presented as equivalent to the LLM agent. Model composition receives
synthetic result data but never receives a confirmation token.

The planner declares a structured `conversation_relation` and an explicit
`inherit_fields` list. A deterministic resolver applies a server-owned
allowlist and records whether each resolved field came from the current
message, a previous read, or authoritative actor context. The local planner
uses parsed slot shape as its fallback; it does not maintain a general
follow-up keyword list.

## Grounded policy retrieval

Policy Markdown is split by authored section and indexed in process with
English normalization, Chinese aliases, and character trigrams. Hybrid
retrieval applies IDF overlap, heading boosts, fuzzy similarity, complementary
section reranking, a minimum evidence score, and concept coverage.

```text
policy question → hybrid candidates → coverage rerank → score + coverage gate
                                                       ├─ met → extractive answer + citations
                                                       └─ unmet → explicit grounded refusal
```

The response exposes source ID, title, section, repository path, and a short
supporting excerpt. Policy retrieval never grants workforce-data access and
does not participate in write execution.

## Safe analytics compiler

The model may select an allowlisted analytics dimension, metric, and filters;
it cannot provide SQL. Core API adds actor row scope and compiles one
parameterized aggregate query under SQLite query-only mode. See
[advanced RAG and safe SQL](advanced-rag-and-safe-sql.md).

## Observability boundary

The AI API generates or validates a request ID, emits metadata-only structured
logs, and exports low-cardinality request and intent counters. It deliberately
does not log prompts, answers, actor IDs, tokens, policy excerpts, or workforce
records. Metrics are process-local and reset when the container restarts. A
separate SQLite Agent audit survives restarts and stores only request ID, role,
mode, planned intent, tool names, status, authorization outcome, latency, and
time. Only an admin can query it.

## Write-operation flow

```text
User request → AI proposes single/batch action → dry-run preview → user confirmation → atomic demo API write → audit event
```

Core validates exact duplicates and cumulative per-person/day hours at both
preview and confirmation. Totals above 8 hours are visible warnings; totals
above 24 hours and duplicate non-rejected records are blocked atomically.

Personal suggestions are a separate read path. They are derived from the
actor's own recent synthetic entries and active memberships, never create a
confirmation token, and are not treated as authorization to write.

Approval proposals name one exact time entry and one explicit decision. The
Core API validates manager/admin scope and submitted state at dry-run time and
again after the user separately confirms the actor-bound token.

Draft editing, deletion, submission, withdrawal, and batch approval use the
same boundary. Ownership, role, membership, and current status are validated
again when the single-use token is consumed.

The AI API must enforce role-aware filtering server-side. The browser is never the authorization boundary.

## MCP and report boundary

The MCP service forwards an explicit fictional actor to Core API and inherits
the same server-side row scope. Preview tools hide confirmation credentials
from model-visible output and expose no confirmation tool. See
[MCP and connector boundaries](mcp-and-connectors.md).

CSV, XLSX, and PDF exporters all reuse the same scoped time-entry query. The
model returns only a structured report descriptor; trusted Next.js routes build
the actual download URL and forward the actor server-side.
