# Evaluation

The publishable deterministic set is `services/ai-api/evals/cases.jsonl`, with
a broader 120-case benchmark in `services/ai-api/evals/benchmark_cases.jsonl`.
The benchmark is split across role scope, analytics, RAG, write safety,
security, and conversation. It covers:

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

Run the metrics reporter against a live stack:

```bash
python services/ai-api/scripts/run_agent_eval.py --base-url http://localhost:8000
```

The reporter prints total/category pass rates and a bounded failure list. The
120 cases are authored for this synthetic AcmeWorks project and contain no
source-project prompts or data.

The deterministic subset is a regression gate and the broader set is a
repeatable benchmark; neither is a claim of broad natural-language accuracy.
