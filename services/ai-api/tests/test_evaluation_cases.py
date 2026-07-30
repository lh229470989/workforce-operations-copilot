import json
from pathlib import Path

import pytest

CASES = [
    json.loads(line)
    for line in (
        Path(__file__).resolve().parents[1] / "evals" / "cases.jsonl"
    ).read_text("utf-8").splitlines()
    if line.strip()
]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_authored_evaluation_case(client, case):
    """Run the publishable prompt set through the same HTTP contract as the UI."""

    response = client.post(
        "/chat",
        headers={"X-Actor-ID": str(case["actor_id"])},
        json={"message": case["message"]},
    )
    body = response.json()

    assert response.status_code == 200
    assert case["expected_text"].casefold() in body["message"].casefold()
    if expected_tool := case.get("expected_tool"):
        assert expected_tool in [
            event["name"] for event in body["tool_events"]
        ]
    if "expected_citation" in case:
        citation_ids = [
            citation["source_id"] for citation in body["citations"]
        ]
        if case["expected_citation"]:
            assert case["expected_citation"] in citation_ids
        else:
            assert citation_ids == []
    if "expect_confirmation" in case:
        assert bool(body["confirmation"]) is case["expect_confirmation"]
