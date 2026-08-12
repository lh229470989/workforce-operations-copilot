import asyncio

import pytest

from app.schemas import AgentPlan
from app.persistent_state import PersistentStateStore
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


def test_sqlite_session_survives_store_restart_and_remains_actor_bound(tmp_path):
    path = str(tmp_path / "state.db")
    first = PersistentStateStore(path, ttl_seconds=60, max_turns=2)
    record = asyncio.run(first.open(3, None))
    asyncio.run(
        first.append(
            record.session_id,
            3,
            user_message="Which projects can I see?",
            assistant_message="Apollo",
            plan=AgentPlan(intent="list_projects"),
        )
    )

    restarted = PersistentStateStore(path, ttl_seconds=60, max_turns=2)
    snapshot = asyncio.run(restarted.open(3, record.session_id))
    assert snapshot.turns[0].user_message == "Which projects can I see?"
    with pytest.raises(SessionActorMismatchError):
        asyncio.run(restarted.open(2, record.session_id))


def test_persistent_state_physically_purges_expired_private_data(tmp_path):
    now = [100.0]
    store = PersistentStateStore(
        str(tmp_path / "state.db"),
        ttl_seconds=10,
        max_turns=2,
        clock=lambda: now[0],
    )
    session = asyncio.run(store.open(3, None))
    preference_action = asyncio.run(
        store.prepare_preferences(3, {"preferred_language": "zh"})
    )

    now[0] = 1001.0
    purged = asyncio.run(store.cleanup_expired())

    assert purged == {
        "sessions": 1,
        "preference_actions": 1,
        "memory_actions": 0,
    }
    replacement = asyncio.run(store.open(2, session.session_id))
    assert replacement.actor_id == 2
    with pytest.raises(KeyError):
        asyncio.run(
            store.confirm_preferences(
                3, preference_action["confirmation_token"]
            )
        )
