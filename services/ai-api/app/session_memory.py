"""Actor-bound, process-local storage for short conversation history."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4

from .schemas import AgentPlan, ConversationTurn


class SessionActorMismatchError(Exception):
    """Raised when a conversation session is accessed by another actor."""

    pass


@dataclass
class SessionRecord:
    """Internal session state; callers receive snapshots rather than this object."""

    session_id: str
    actor_id: int
    expires_at: float
    turns: list[ConversationTurn] = field(default_factory=list)


class SessionMemory:
    """Keep a bounded conversation history without persistent user profiling."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 30 * 60,
        max_turns: int = 10,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self.clock = clock
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def open(
        self, actor_id: int, requested_session_id: str | None
    ) -> SessionRecord:
        """Open or create a session and return an isolated snapshot."""

        async with self._lock:
            now = self.clock()
            self._purge_expired(now)
            session_id = requested_session_id or str(uuid4())
            record = self._sessions.get(session_id)

            # The actor check is server-side because a browser-controlled
            # session ID must not grant access to another demo user's context.
            if record is not None and record.actor_id != actor_id:
                raise SessionActorMismatchError
            if record is None:
                record = SessionRecord(
                    session_id=session_id,
                    actor_id=actor_id,
                    expires_at=now + self.ttl_seconds,
                )
                self._sessions[session_id] = record
            else:
                record.expires_at = now + self.ttl_seconds
            # Return a copy so request processing cannot mutate shared state
            # outside the lock.
            return SessionRecord(
                session_id=record.session_id,
                actor_id=record.actor_id,
                expires_at=record.expires_at,
                turns=list(record.turns),
            )

    async def append(
        self,
        session_id: str,
        actor_id: int,
        *,
        user_message: str,
        assistant_message: str,
        plan: AgentPlan,
    ) -> None:
        """Append one completed turn and renew the sliding expiration."""

        async with self._lock:
            record = self._sessions.get(session_id)
            if record is None or record.actor_id != actor_id:
                raise SessionActorMismatchError
            record.turns.append(
                ConversationTurn(
                    user_message=user_message,
                    assistant_message=assistant_message,
                    plan=plan,
                )
            )
            # Bound both prompt size and accidental retention of old messages.
            record.turns = record.turns[-self.max_turns :]
            record.expires_at = self.clock() + self.ttl_seconds

    def _purge_expired(self, now: float) -> None:
        """Remove expired sessions while the caller holds the lock."""

        expired = [
            session_id
            for session_id, record in self._sessions.items()
            if record.expires_at <= now
        ]
        for session_id in expired:
            del self._sessions[session_id]
