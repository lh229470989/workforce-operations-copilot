# Evaluation

The publishable evaluation set is
`services/ai-api/evals/cases.jsonl`. It covers:

- English and Chinese role-scoped reads;
- date, project, status, and limit parsing;
- manager approval queue reads and explicit approval dry-runs;
- hybrid compound-policy retrieval, evidence coverage, and refusal;
- multi-tool comparison and declarative safe SQL analysis;
- persistent privacy preferences and two-step state deletion;
- incomplete write requests that must not produce confirmation.

`tests/test_evaluation_cases.py` runs every case through the public `/chat`
HTTP contract. Dedicated tests additionally cover actor/session substitution,
conversation field provenance, write non-inheritance, knowledge retrieval,
raw-SQL rejection, Core row scope, prompt checksums, persistent sessions,
request IDs, security headers, and metrics.

Run:

```bash
cd services/ai-api
pytest tests/test_evaluation_cases.py
pytest
```

The evaluation set is intentionally small and deterministic. It is a
regression and safety gate, not a claim of broad natural-language accuracy.
