import json
from collections import Counter
from pathlib import Path


def test_publishable_benchmark_has_breadth_and_safe_contracts():
    path = Path(__file__).parents[1] / "evals" / "benchmark_cases.jsonl"
    cases = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]
    categories = Counter(case["category"] for case in cases)

    assert 100 <= len(cases) <= 200
    assert len({case["id"] for case in cases}) == len(cases)
    assert set(categories) == {
        "role_scope", "analytics", "rag", "write_safety", "security", "conversation"
    }
    assert min(categories.values()) >= 15
    assert all(case["must_not_contain"] for case in cases)
