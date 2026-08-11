# Security Model

## Supported scope

This repository is a local fictional demonstration. It must not be connected
to production identity, HR, billing, customer, or source-control systems.
Report a suspected issue privately to the repository owner before creating a
public issue containing exploit details.

## Trust boundaries

- The browser chooses one of three fixed demo identities, but does not enforce
  authorization.
- Core API reloads the actor and applies record-level role rules for every
  operation.
- AI API may plan an operation but cannot bypass Core API authorization.
- Every data-changing operation requires a server-created dry-run token and a
  separate explicit confirmation request.
- Conversation sessions are actor-bound, bounded, expiring, and stored in a
  dedicated local state database with user-controlled deletion.
- Policy answers require repository evidence, coverage thresholds, and citations.

## Primary threats and controls

| Threat | Control |
| --- | --- |
| Actor or session substitution | Server actor lookup and actor-bound session IDs |
| Prompt-driven authorization bypass | Fixed tool contracts plus Core API RBAC |
| Accidental write | Dry-run token followed by explicit confirmation |
| Stale role or project context | Authoritative actor context refreshed per request |
| Unsafe contextual write completion | Read-field inheritance allowlist |
| Policy hallucination | Retrieval threshold, extractive answer, citations, refusal |
| Model-generated SQL or data exfiltration | No SQL-text field; allowlisted analytics spec, actor scope, parameterized compiler, query-only connection |
| Persistent-context overreach | Minimal preferences, fresh authorization, TTL, history opt-out, two-step deletion |
| Secret publication | Ignore rules, local publication scan, CI scan |
| Sensitive telemetry | Metadata-only logs and low-cardinality metrics |
| Browser injection or framing | CSP, no-sniff, no-referrer, and frame denial headers |
| Container privilege | Non-root runtime users |

## Known limitations

- Demo identity headers are not real authentication.
- Process-local rate limits and durable audit shipping are not implemented.
- Metrics are in memory and are not an enterprise monitoring system.
- The static Next.js build permits its framework bootstrap inline script.
  Moving to nonce-based CSP requires dynamic request-time rendering.
- Dependency audit results can change after publication and must be rerun.
- SQLite state is a single-node demo store, not encrypted enterprise memory or
  a multi-region retention system.
