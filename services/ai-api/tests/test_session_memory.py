import asyncio

import pytest

from app.schemas import AgentPlan
from app.session_memory import SessionActorMismatchError, SessionMemory


def test_session_is_actor_bound_and_expires():
    now = [100.0]
    memory = SessionMemory(ttl_seconds=10, clock=lambda: now[0])
    record = asyncio.run(memory.open(3, None))

    with pytest.raises(SessionActorMismatchError):
        asyncio.run(memory.open(2, record.session_id))

    now[0] = 111.0
    replacement = asyncio.run(memory.open(2, record.session_id))
    assert replacement.actor_id == 2
    assert replacement.turns == []


def test_session_caps_recent_turns():
    memory = SessionMemory(max_turns=2)
    record = asyncio.run(memory.open(3, None))
    for index in range(3):
        asyncio.run(
            memory.append(
                record.session_id,
                3,
                user_message=f"question {index}",
                assistant_message=f"answer {index}",
                plan=AgentPlan(intent="list_projects"),
            )
        )

    snapshot = asyncio.run(memory.open(3, record.session_id))
    assert [turn.user_message for turn in snapshot.turns] == [
        "question 1",
        "question 2",
    ]
