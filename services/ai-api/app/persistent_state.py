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
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    actor_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS memories_actor_idx
                    ON memories(actor_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS memory_actions (
                    token TEXT PRIMARY KEY,
                    actor_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    memory_id TEXT,
                    payload_json TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    consumed_at REAL
                );
                CREATE TABLE IF NOT EXISTS agent_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    tool_names_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    authorization_outcome TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS agent_audit_created_idx
                    ON agent_audit(created_at DESC);
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
        memory_actions = db.execute(
            "DELETE FROM memory_actions WHERE expires_at <= ?", (now,)
        ).rowcount
        return {
            "sessions": sessions,
            "preference_actions": actions,
            "memory_actions": memory_actions,
        }

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
                        "structured_memories",
                        "pending_preference_actions",
                        "pending_memory_actions",
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
                    db.execute("DELETE FROM memories WHERE actor_id = ?", (actor_id,))
                    db.execute(
                        "DELETE FROM memory_actions WHERE actor_id = ?", (actor_id,)
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

    async def list_memories(self, actor_id: int) -> list[dict[str, Any]]:
        """Return only the current actor's explicit, structured memories."""

        async with self._lock:
            with self._connect() as db:
                rows = db.execute(
                    "SELECT id, category, value, created_at, updated_at "
                    "FROM memories WHERE actor_id = ? ORDER BY updated_at DESC",
                    (actor_id,),
                ).fetchall()
                return [dict(row) for row in rows]

    async def prepare_memory(
        self,
        actor_id: int,
        action_type: str,
        payload: dict[str, Any],
        *,
        memory_id: str | None = None,
    ) -> dict[str, Any]:
        """Create an actor-bound proposal; no memory changes during dry-run."""

        async with self._lock:
            token = str(uuid4())
            expires_at = self.clock() + 15 * 60
            with self._connect() as db:
                current = None
                if memory_id is not None:
                    row = db.execute(
                        "SELECT id, category, value FROM memories "
                        "WHERE id = ? AND actor_id = ?",
                        (memory_id, actor_id),
                    ).fetchone()
                    if row is None:
                        raise KeyError("Memory not found")
                    current = dict(row)
                if action_type == "create":
                    memory_count = db.execute(
                        "SELECT COUNT(*) FROM memories WHERE actor_id = ?", (actor_id,)
                    ).fetchone()[0]
                    if memory_count >= 20:
                        raise ValueError("Structured memory limit reached")
                    preview = payload
                elif action_type == "update":
                    preview = {**(current or {}), **payload}
                elif action_type == "delete":
                    preview = current or {}
                else:
                    raise ValueError("Unsupported memory action")
                db.execute(
                    "INSERT INTO memory_actions VALUES (?, ?, ?, ?, ?, ?, NULL)",
                    (
                        token,
                        actor_id,
                        action_type,
                        memory_id,
                        json.dumps(payload),
                        expires_at,
                    ),
                )
                return {
                    "action": f"{action_type}_memory",
                    "preview": preview,
                    "confirmation_token": token,
                    "expires_at": expires_at,
                }

    async def confirm_memory(
        self, actor_id: int, token: str
    ) -> dict[str, Any]:
        """Apply one fresh memory proposal after explicit confirmation."""

        async with self._lock:
            now = self.clock()
            with self._connect() as db:
                action = db.execute(
                    "SELECT * FROM memory_actions WHERE token = ?", (token,)
                ).fetchone()
                if action is None:
                    raise KeyError("Memory action not found")
                if action["actor_id"] != actor_id:
                    raise PermissionError("Memory action belongs to another actor")
                if action["consumed_at"] is not None:
                    raise RuntimeError("Memory action already consumed")
                if action["expires_at"] < now:
                    raise TimeoutError("Memory action expired")
                payload = json.loads(action["payload_json"])
                action_type = action["action_type"]
                memory_id = action["memory_id"] or str(uuid4())
                if action_type == "create":
                    db.execute(
                        "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            memory_id,
                            actor_id,
                            payload["category"],
                            payload["value"],
                            now,
                            now,
                        ),
                    )
                elif action_type == "update":
                    existing = db.execute(
                        "SELECT * FROM memories WHERE id = ? AND actor_id = ?",
                        (memory_id, actor_id),
                    ).fetchone()
                    if existing is None:
                        raise KeyError("Memory not found")
                    db.execute(
                        "UPDATE memories SET category = ?, value = ?, updated_at = ? "
                        "WHERE id = ? AND actor_id = ?",
                        (
                            payload.get("category", existing["category"]),
                            payload.get("value", existing["value"]),
                            now,
                            memory_id,
                            actor_id,
                        ),
                    )
                elif action_type == "delete":
                    deleted = db.execute(
                        "DELETE FROM memories WHERE id = ? AND actor_id = ?",
                        (memory_id, actor_id),
                    ).rowcount
                    if deleted == 0:
                        raise KeyError("Memory not found")
                db.execute(
                    "UPDATE memory_actions SET consumed_at = ? WHERE token = ?",
                    (now, token),
                )
                if action_type == "delete":
                    return {"id": memory_id, "deleted": True}
                row = db.execute(
                    "SELECT id, category, value, created_at, updated_at "
                    "FROM memories WHERE id = ?",
                    (memory_id,),
                ).fetchone()
                return dict(row)

    async def append_agent_audit(self, record: dict[str, Any]) -> None:
        """Persist operational metadata, never prompts, answers, or tool payloads."""

        async with self._lock:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO agent_audit "
                    "(request_id, actor_role, mode, intent, tool_names_json, status, "
                    "authorization_outcome, latency_ms, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record["request_id"],
                        record["actor_role"],
                        record["mode"],
                        record["intent"],
                        json.dumps(record.get("tool_names", [])),
                        record["status"],
                        record["authorization_outcome"],
                        record["latency_ms"],
                        self.clock(),
                    ),
                )

    async def list_agent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        async with self._lock:
            with self._connect() as db:
                rows = db.execute(
                    "SELECT * FROM agent_audit ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
                return [
                    {
                        **{
                            key: value
                            for key, value in dict(row).items()
                            if key != "tool_names_json"
                        },
                        "tool_names": json.loads(row["tool_names_json"]),
                    }
                    for row in rows
                ]
