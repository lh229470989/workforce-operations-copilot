import os
from pathlib import Path

from app.knowledge_base import PolicyKnowledgeBase


KNOWLEDGE_ROOT = (
    Path(os.environ["KNOWLEDGE_BASE_PATH"])
    if "KNOWLEDGE_BASE_PATH" in os.environ
    else Path(__file__).resolve().parents[3] / "knowledge-base"
)


def test_retrieves_a_grounded_deadline_answer():
    knowledge_base = PolicyKnowledgeBase(KNOWLEDGE_ROOT)

    assert all(
        chunk.relative_path != "knowledge-base/README.md"
        for chunk in knowledge_base.chunks
    )
    result = knowledge_base.search(
        "What is the weekly time submission deadline?"
    )

    assert result is not None
    assert "12:00 noon" in result.answer
    assert result.citations[0].source_id == "time-reporting"
    assert result.citations[0].section == "Weekly submission deadline"


def test_supports_chinese_policy_terms_against_english_source():
    knowledge_base = PolicyKnowledgeBase(KNOWLEDGE_ROOT)

    result = knowledge_base.search("工时提交截止时间是什么？")

    assert result is not None
    assert result.citations[0].source_id == "time-reporting"


def test_refuses_when_policy_evidence_is_too_weak():
    knowledge_base = PolicyKnowledgeBase(KNOWLEDGE_ROOT)

    assert knowledge_base.search("What is the spaceship parking policy?") is None
