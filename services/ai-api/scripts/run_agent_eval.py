"""Run the publishable benchmark against a live AI API and print JSON metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).parents[1] / "evals" / "benchmark_cases.jsonl",
    )
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.cases.read_text("utf-8").splitlines() if line]
    outcomes: Counter[str] = Counter()
    category_passes: Counter[str] = Counter()
    category_totals: Counter[str] = Counter()
    failures = []
    for case in cases:
        request = Request(
            f"{args.base_url.rstrip('/')}/chat",
            data=json.dumps({"message": case["message"]}).encode(),
            headers={"Content-Type": "application/json", "X-Actor-ID": str(case["actor_id"])},
        )
        category_totals[case["category"]] += 1
        try:
            with urlopen(request, timeout=30) as response:
                body = json.load(response)
            tool_names = [event["name"] for event in body.get("tool_events", [])]
            checks = [
                bool(body.get("confirmation")) is case["expect_confirmation"],
                not case.get("expected_tool") or case["expected_tool"] in tool_names,
                # Scoped tool data can legitimately include fictional AcmeWorks
                # emails. Leakage checks apply to composed prose, where the
                # model must not volunteer private identifiers or credentials.
                all(marker not in body.get("message", "").casefold() for marker in case["must_not_contain"]),
            ]
            if all(checks):
                outcomes["passed"] += 1
                category_passes[case["category"]] += 1
            else:
                outcomes["failed"] += 1
                failures.append({"id": case["id"], "tools": tool_names, "checks": checks})
        except Exception as exc:
            outcomes["error"] += 1
            failures.append({"id": case["id"], "error": type(exc).__name__})
    report = {
        "total": len(cases),
        "passed": outcomes["passed"],
        "pass_rate": round(outcomes["passed"] / len(cases), 4),
        "categories": {
            name: {
                "passed": category_passes[name],
                "total": total,
                "pass_rate": round(category_passes[name] / total, 4),
            }
            for name, total in sorted(category_totals.items())
        },
        "failures": failures[:20],
    }
    print(json.dumps(report, indent=2))
    return 0 if outcomes["passed"] == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
