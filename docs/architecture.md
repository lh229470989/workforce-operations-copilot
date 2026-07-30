# Target Architecture

## Components

| Component | Responsibility | Public-demo constraint |
| --- | --- | --- |
| `apps/web` | Chat, data workspace, approval cards, charts | Only synthetic data |
| `services/ai-api` | Agent orchestration, RAG, authorization, tool dispatch | No production adapters |
| `services/demo-core-api` | Mock internal workforce API | SQLite and seeded fictional data |
| `knowledge-base` | Fictional policies used for retrieval | Authored from scratch |

## Web request boundary

The Next.js application uses server-side route handlers for chat and explicit
confirmation. The browser selects only one of the three known demo personas.
Route handlers forward that actor ID, while the Core API loads the actor and
role from SQLite and applies record-level authorization.

## Context layers

1. **Authoritative actor context** is refreshed from Core API for every chat:
   role, visible departments/projects, and recent fictional time entries.
2. **Short conversation context** is process-local, actor-bound, capped at 10
   turns, and expires after 30 minutes by default.
3. **Long-term memory** is intentionally not implemented. Adding cross-session
   retention requires an explicit retention, deletion, and privacy design.

Conversation context may fill omitted filters for read-only follow-ups. It
never fills missing fields for a draft or confirmation.

The planner declares a structured `conversation_relation` and an explicit
`inherit_fields` list. A deterministic resolver applies a server-owned
allowlist and records whether each resolved field came from the current
message, a previous read, or authoritative actor context. The local planner
uses parsed slot shape as its fallback; it does not maintain a general
follow-up keyword list.

## Grounded policy retrieval

Policy Markdown is split by authored section and indexed in process with
English tokens, Chinese aliases, and character bigrams. Retrieval applies
normalized IDF overlap, heading boosts, and a minimum evidence score.

```text
policy question → retrieve sections → evidence threshold
                                      ├─ met → extractive answer + citations
                                      └─ unmet → explicit grounded refusal
```

The response exposes source ID, title, section, repository path, and a short
supporting excerpt. Policy retrieval never grants workforce-data access and
does not participate in write execution.

## Observability boundary

The AI API generates or validates a request ID, emits metadata-only structured
logs, and exports low-cardinality request and intent counters. It deliberately
does not log prompts, answers, actor IDs, tokens, policy excerpts, or workforce
records. Metrics are process-local and reset when the container restarts.

## Write-operation flow

```text
User request → AI proposes action → dry-run preview → user confirmation → demo API write → audit event
```

The AI API must enforce role-aware filtering server-side. The browser is never the authorization boundary.
