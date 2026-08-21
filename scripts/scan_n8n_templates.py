#!/usr/bin/env python3
"""Fail closed when public n8n exports violate the integration boundary."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "integrations" / "n8n"
FILES = {
    "a": TEMPLATE_ROOT / "workflow-a-calendar-ingest.json",
    "b": TEMPLATE_ROOT / "workflow-b-confirmed-slack.json",
}
PROHIBITED = re.compile(
    r"https?://(?!www\.googleapis\.com/auth/calendar\.readonly)|"
    r"hooks\.slack\.com|@(?:gmail|googlemail)\.com|"
    r"(?:access|refresh|client)[_-]?token|client[_-]?secret|"
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
    re.IGNORECASE,
)


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["active"] is False, f"{path.name} must import disabled"
    assert data["settings"]["executionOrder"] == "v1"
    assert data.get("pinData") == {}, f"{path.name} must not contain pinned data"
    assert len({node["id"] for node in data["nodes"]}) == len(data["nodes"])
    serialized = json.dumps(data, sort_keys=True)
    assert "credentials" not in serialized.lower()
    assert not PROHIBITED.search(serialized), f"prohibited value in {path.name}"
    return data


def edges(workflow: dict) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for source, outputs in workflow["connections"].items():
        result[source] = {
            edge["node"] for branch in outputs.get("main", []) for edge in branch
        }
    return result


def reachable(graph: dict[str, set[str]], start: str, target: str) -> bool:
    pending, seen = [start], set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(graph.get(node, ()))
    return False


def validate_a(workflow: dict) -> None:
    nodes = {node["name"]: node for node in workflow["nodes"]}
    graph = edges(workflow)
    required = [
        "Every 15 Minutes",
        "Read Dedicated Calendar (readonly credential required)",
        "Filter Map Validate and Sign WorkEvent",
        "Create Suggestion Only",
    ]
    assert all(name in nodes for name in required)
    assert nodes[required[1]]["type"] == "n8n-nodes-base.googleCalendar"
    assert reachable(graph, required[0], required[-1])
    assert not any(node["type"] == "n8n-nodes-base.wait" for node in nodes.values())
    code = nodes[required[2]]["parameters"]["jsCode"]
    for marker in (
        "acme_work_event",
        "COPILOT_INGEST_HMAC_SECRET",
        "X-Acme-Idempotency-Key",
        "duration % 15",
        "JSON.stringify(event)",
    ):
        assert marker in code
    assert "attendees" not in code and "description:String(e.description" not in code
    assert nodes[required[-1]]["parameters"]["url"] == "={{ $env.COPILOT_INGEST_URL }}"


def validate_b(workflow: dict) -> None:
    nodes = {node["name"]: node for node in workflow["nodes"]}
    graph = edges(workflow)
    order = [
        "Confirmed Event Webhook Raw Body",
        "Verify HMAC Then Validate Confirmed Event",
        "Sign Delivery Claim",
        "Claim Before Slack",
        "Claim Granted?",
        "Build Fixed Slack Payload",
        "One Message Per Second Gate",
        "Slack Incoming Webhook",
        "Classify Result and Sign Completion",
        "Complete Delivery Ledger",
    ]
    assert all(name in nodes for name in order)
    assert nodes[order[0]]["parameters"]["options"]["rawBody"] is True
    for source, target in zip(order, order[1:]):
        assert reachable(graph, source, target), f"{source} must precede {target}"
    assert not reachable(graph, order[0], order[7]) or reachable(graph, order[4], order[7])
    assert nodes[order[7]]["parameters"]["url"] == "={{ $env.SLACK_WEBHOOK_URL }}"
    verify = nodes[order[1]]["parameters"]["jsCode"]
    assert "timingSafeEqual" in verify and "COPILOT_OUTBOUND_HMAC_SECRET" in verify
    slack = nodes[order[5]]["parameters"]["jsCode"]
    for forbidden in ("description", "calendar", "email", "event_id"):
        assert forbidden not in slack.lower()
    wait = nodes[order[6]]["parameters"]
    assert wait == {"amount": 1, "unit": "seconds"}


def main() -> None:
    a, b = load(FILES["a"]), load(FILES["b"])
    validate_a(a)
    validate_b(b)
    print("n8n public templates validated: disabled, credential-free, ordered, bounded.")


if __name__ == "__main__":
    main()
