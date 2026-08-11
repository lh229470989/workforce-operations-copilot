"""SQLite-backed, actor-bound sessions and privacy preferences."""

import asyncio
import json
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from .schemas import AgentPlan, ConversationTurn
from .session_memory import SessionActorMismatchError, SessionRecord


class PersistentStateStore:
    """Persist bounded history without treating preferences as authorization."""

    def __init__(
        self,
        path: str,
        *,
        ttl_seconds: int,
        max_turns: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self.clock = clock
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    actor_id INTEGER NOT NULL,
                    expires_at REAL NOT NULL,
                    turns_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    actor_id INTEGER PRIMARY KEY,
                    history_enabled INTEGER NOT NULL DEFAULT 1,
                    preferred_language TEXT NOT NULL DEFAULT 'auto',
                    preferred_project_id INTEGER,
                    response_detail TEXT NOT NULL DEFAULT 'standard',
                    report_format TEXT NOT NULL DEFAULT 'summary',
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS preference_actions (
                    token TEXT PRIMARY KEY,
                    actor_id INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL
                );
                """
            )
            columns = {
                row["name"] for row in db.execute("PRAGMA table_info(preferences)")
            }
            if "response_detail" not in columns:
                db.execute(
                    "ALTER TABLE preferences ADD COLUMN response_detail TEXT NOT NULL DEFAULT 'standard'"
                )
            if "report_format" not in columns:
                db.execute(
                    "ALTER TABLE preferences ADD COLUMN report_format TEXT NOT NULL DEFAULT 'summary'"
                )
            self._cleanup_expired_records(db, self.clock())

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _cleanup_expired_records(
        db: sqlite3.Connection, now: float
    ) -> dict[str, int]:
        """Delete expired private state while using the caller's transaction."""

        sessions = db.execute(
            "DELETE FROM sessions WHERE expires_at <= ?", (now,)
        ).rowcount
        actions = db.execute(
            "DELETE FROM preference_actions WHERE expires_at <= ?", (now,)
        ).rowcount
        return {"sessions": sessions, "preference_actions": actions}

    async def cleanup_expired(self) -> dict[str, int]:
        """Physically purge expired sessions and preference proposals."""

        async with self._lock:
            with self._connect() as db:
                return self._cleanup_expired_records(db, self.clock())

    async def open(
        self, actor_id: int, requested_session_id: str | None
    ) -> SessionRecord:
        async with self._lock:
            now = self.clock()
            session_id = requested_session_id or str(uuid4())
            with self._connect() as db:
                self._cleanup_expired_records(db, now)
                row = db.execute(
                    "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
                ).fetchone()
                if row is not None and row["actor_id"] != actor_id:
                    raise SessionActorMismatchError
                turns = (
                    [
                        ConversationTurn.model_validate(item)
                        for item in json.loads(row["turns_json"])
                    ]
                    if row is not None
                    else []
                )
                expires_at = now + self.ttl_seconds
                db.execute(
                    "INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)",
                    (
                        session_id,
                        actor_id,
                        expires_at,
                        json.dumps(
                            [turn.model_dump(mode="json") for turn in turns]
                        ),
                    ),
                )
            return SessionRecord(session_id, actor_id, expires_at, turns)

    async def append(
        self,
        session_id: str,
        actor_id: int,
        *,
        user_message: str,
        assistant_message: str,
        plan: AgentPlan,
    ) -> None:
        async with self._lock:
            with self._connect() as db:
                row = db.execute(
                    "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
                ).fetchone()
                if row is None or row["actor_id"] != actor_id:
                    raise SessionActorMismatchError
                preference = self._get_preferences(db, actor_id)
                turns = (
                    []
                    if not preference["history_enabled"]
                    else [
                        ConversationTurn.model_validate(item)
                        for item in json.loads(row["turns_json"])
                    ]
                )
                if preference["history_enabled"]:
                    turns.append(
                        ConversationTurn(
                            user_message=user_message,
                            assistant_message=assistant_message,
                            plan=plan,
                        )
                    )
                    turns = turns[-self.max_turns :]
                db.execute(
                    "UPDATE sessions SET expires_at = ?, turns_json = ? "
                    "WHERE session_id = ?",
                    (
                        self.clock() + self.ttl_seconds,
                        json.dumps(
                            [turn.model_dump(mode="json") for turn in turns]
                        ),
                        session_id,
                    ),
                )

    def _get_preferences(
        self, db: sqlite3.Connection, actor_id: int
    ) -> dict[str, Any]:
        row = db.execute(
            "SELECT * FROM preferences WHERE actor_id = ?", (actor_id,)
        ).fetchone()
        if row is None:
            return {
                "actor_id": actor_id,
                "history_enabled": True,
                "preferred_language": "auto",
                "preferred_project_id": None,
                "response_detail": "standard",
                "report_format": "summary",
            }
        return {
            "actor_id": actor_id,
            "history_enabled": bool(row["history_enabled"]),
            "preferred_language": row["preferred_language"],
            "preferred_project_id": row["preferred_project_id"],
            "response_detail": row["response_detail"],
            "report_format": row["report_format"],
        }

    async def get_preferences(self, actor_id: int) -> dict[str, Any]:
        async with self._lock:
            with self._connect() as db:
                return self._get_preferences(db, actor_id)

    async def prepare_preferences(
        self, actor_id: int, updates: dict[str, Any]
    ) -> dict[str, Any]:
        async with self._lock:
            token = str(uuid4())
            expires_at = self.clock() + 15 * 60
            with self._connect() as db:
                current = self._get_preferences(db, actor_id)
                preview = {**current, **updates}
                db.execute(
                    "INSERT INTO preference_actions VALUES (?, ?, ?, ?, NULL)",
                    (token, actor_id, json.dumps(updates), expires_at),
                )
            return {
                "action": "update_preferences",
                "preview": preview,
                "confirmation_token": token,
                "expires_at": expires_at,
            }

    async def prepare_state_deletion(self, actor_id: int) -> dict[str, Any]:
        async with self._lock:
            token = str(uuid4())
            expires_at = self.clock() + 15 * 60
            with self._connect() as db:
                db.execute(
                    "INSERT INTO preference_actions VALUES (?, ?, ?, ?, NULL)",
                    (
                        token,
                        actor_id,
                        json.dumps({"__delete_all__": True}),
                        expires_at,
                    ),
                )
            return {
                "action": "delete_private_state",
                "preview": {
                    "actor_id": actor_id,
                    "deletes": [
                        "conversation_sessions",
                        "preferences",
                        "pending_preference_actions",
                    ],
                },
                "confirmation_token": token,
                "expires_at": expires_at,
            }

    async def confirm_preferences(
        self, actor_id: int, token: str
    ) -> dict[str, Any]:
        async with self._lock:
            now = self.clock()
            with self._connect() as db:
                action = db.execute(
                    "SELECT * FROM preference_actions WHERE token = ?", (token,)
                ).fetchone()
                if action is None:
                    raise KeyError("Preference action not found")
                if action["actor_id"] != actor_id:
                    raise PermissionError(
                        "Preference action belongs to another actor"
                    )
                if action["consumed_at"] is not None:
                    raise RuntimeError("Preference action already consumed")
                if action["expires_at"] < now:
                    raise TimeoutError("Preference action expired")
                payload = json.loads(action["payload_json"])
                if payload.get("__delete_all__") is True:
                    db.execute(
                        "DELETE FROM sessions WHERE actor_id = ?", (actor_id,)
                    )
                    db.execute(
                        "DELETE FROM preferences WHERE actor_id = ?", (actor_id,)
                    )
                    db.execute(
                        "DELETE FROM preference_actions WHERE actor_id = ?",
                        (actor_id,),
                    )
                    return {
                        "actor_id": actor_id,
                        "history_enabled": True,
                        "preferred_language": "auto",
                        "preferred_project_id": None,
                        "response_detail": "standard",
                        "report_format": "summary",
                        "deleted": True,
                    }
                current = self._get_preferences(db, actor_id)
                updated = {**current, **payload}
                db.execute(
                    "INSERT OR REPLACE INTO preferences "
                    "(actor_id, history_enabled, preferred_language, preferred_project_id, response_detail, report_format, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        actor_id,
                        int(updated["history_enabled"]),
                        updated["preferred_language"],
                        updated["preferred_project_id"],
                        updated["response_detail"],
                        updated["report_format"],
                        now,
                    ),
                )
                db.execute(
                    "UPDATE preference_actions SET consumed_at = ? WHERE token = ?",
                    (now, token),
                )
                if not updated["history_enabled"]:
                    db.execute(
                        "DELETE FROM sessions WHERE actor_id = ?", (actor_id,)
                    )
                return updated
