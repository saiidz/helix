"""Local-first user memory and conversation persistence for the single-owner prototype."""
from __future__ import annotations

import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

MEMORY_KINDS = {"profile", "preference", "person", "project", "episodic", "other"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_'-]{3,}", text.lower())
        if token not in {"the", "and", "that", "this", "with", "from", "have", "your", "you", "are", "for"}
    }


class MemoryStore:
    """SQLite-backed memory store.

    This build is intentionally single-owner. A user_id column is included now so
    the schema can later migrate to authenticated multi-user storage without
    changing the conceptual model.
    """

    def __init__(self, path: Path, user_id: str = "local-owner"):
        self.path = path
        self.user_id = user_id
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0,
                importance REAL NOT NULL DEFAULT 0.5,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_memories_user_active
                         ON memories(user_id, active, updated_at DESC)""")
            c.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                         ON conversations(user_id, updated_at DESC)""")
            c.execute("""CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_messages_conversation
                         ON conversation_messages(conversation_id, id)""")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _memory_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "kind": row["kind"],
            "content": row["content"],
            "source": row["source"],
            "pinned": bool(row["pinned"]),
            "importance": float(row["importance"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_used_at": row["last_used_at"],
        }

    def add_memory(
        self,
        content: str,
        kind: str = "other",
        source: str = "user",
        pinned: bool = False,
        importance: float = 0.5,
    ) -> dict:
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty")
        if len(content) > 4000:
            raise ValueError("Memory content is too long")
        if kind not in MEMORY_KINDS:
            raise ValueError("Unsupported memory kind")
        if not 0 <= importance <= 1:
            raise ValueError("Importance must be between 0 and 1")

        now = utc_now()
        memory_id = str(uuid.uuid4())

        with self.connect() as c:
            duplicate = c.execute(
                """SELECT * FROM memories
                   WHERE user_id=? AND active=1 AND lower(content)=lower(?)
                   ORDER BY updated_at DESC LIMIT 1""",
                (self.user_id, content),
            ).fetchone()

            if duplicate:
                c.execute(
                    """UPDATE memories
                       SET kind=?, source=?, pinned=?, importance=?, updated_at=?
                       WHERE id=? AND user_id=?""",
                    (kind, source, int(pinned), importance, now, duplicate["id"], self.user_id),
                )
                row = c.execute("SELECT * FROM memories WHERE id=?", (duplicate["id"],)).fetchone()
                return self._memory_dict(row)

            c.execute(
                """INSERT INTO memories
                   (id,user_id,kind,content,source,pinned,importance,active,created_at,updated_at,last_used_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,NULL)""",
                (
                    memory_id,
                    self.user_id,
                    kind,
                    content,
                    source,
                    int(pinned),
                    importance,
                    1,
                    now,
                    now,
                ),
            )
            row = c.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            return self._memory_dict(row)

    def list_memories(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        with self.connect() as c:
            rows = c.execute(
                """SELECT * FROM memories
                   WHERE user_id=? AND active=1
                   ORDER BY pinned DESC, importance DESC, updated_at DESC
                   LIMIT ?""",
                (self.user_id, limit),
            ).fetchall()
        return [self._memory_dict(row) for row in rows]

    def delete_memory(self, memory_id: str) -> bool:
        with self.connect() as c:
            result = c.execute(
                """UPDATE memories
                   SET active=0, updated_at=?
                   WHERE id=? AND user_id=? AND active=1""",
                (utc_now(), memory_id, self.user_id),
            )
            return result.rowcount == 1

    def set_pinned(self, memory_id: str, pinned: bool) -> dict | None:
        with self.connect() as c:
            result = c.execute(
                """UPDATE memories
                   SET pinned=?, updated_at=?
                   WHERE id=? AND user_id=? AND active=1""",
                (int(pinned), utc_now(), memory_id, self.user_id),
            )
            if result.rowcount != 1:
                return None
            row = c.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
            return self._memory_dict(row)

    def retrieve(self, query: str, limit: int = 6) -> list[dict]:
        query_tokens = _tokens(query)
        candidates = self.list_memories(limit=250)
        scored: list[tuple[float, dict]] = []

        for memory in candidates:
            overlap = len(query_tokens & _tokens(memory["content"]))
            if overlap == 0 and not memory["pinned"]:
                continue
            score = overlap * 2.0 + memory["importance"] + (3.0 if memory["pinned"] else 0.0)
            scored.append((score, memory))

        selected = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]

        if selected:
            now = utc_now()
            ids = [item["id"] for item in selected]
            placeholders = ",".join("?" for _ in ids)
            with self.connect() as c:
                c.execute(
                    f"UPDATE memories SET last_used_at=? WHERE user_id=? AND id IN ({placeholders})",
                    (now, self.user_id, *ids),
                )

        return selected

    def capture_explicit(self, text: str) -> dict | None:
        """Capture only explicit memory requests in v0.2."""
        match = re.match(
            r"^\s*(?:please\s+)?remember(?:\s+that)?\s+(.+?)\s*[.!]?\s*$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        content = match.group(1).strip()
        if not content:
            return None

        kind = "other"
        lowered = content.lower()
        if any(term in lowered for term in ("i prefer", "i like", "i dislike", "i don't like")):
            kind = "preference"
        elif any(term in lowered for term in ("my name", "my birthday", "i was born", "my timezone")):
            kind = "profile"
        elif any(term in lowered for term in ("project", "repo", "repository", "codebase", "stack")):
            kind = "project"

        return self.add_memory(content, kind=kind, source="explicit_user", importance=0.8)

    def ensure_conversation(self, conversation_id: str, title: str = "New conversation") -> dict:
        now = utc_now()
        with self.connect() as c:
            row = c.execute(
                "SELECT * FROM conversations WHERE id=? AND user_id=?",
                (conversation_id, self.user_id),
            ).fetchone()
            if row:
                return dict(row)
            c.execute(
                "INSERT INTO conversations VALUES (?,?,?,?,?)",
                (conversation_id, self.user_id, title[:120] or "New conversation", now, now),
            )
            row = c.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            return dict(row)

    def create_conversation(self, title: str = "New conversation") -> dict:
        return self.ensure_conversation(str(uuid.uuid4()), title)

    def save_message(self, conversation_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Unsupported conversation role")
        content = content.strip()
        if not content:
            return

        self.ensure_conversation(conversation_id, content[:80] if role == "user" else "New conversation")
        now = utc_now()

        with self.connect() as c:
            c.execute(
                """INSERT INTO conversation_messages
                   (conversation_id,user_id,role,content,created_at)
                   VALUES (?,?,?,?,?)""",
                (conversation_id, self.user_id, role, content, now),
            )
            if role == "user":
                c.execute(
                    """UPDATE conversations
                       SET title=CASE WHEN title='New conversation' THEN ? ELSE title END,
                           updated_at=?
                       WHERE id=? AND user_id=?""",
                    (content[:80], now, conversation_id, self.user_id),
                )
            else:
                c.execute(
                    "UPDATE conversations SET updated_at=? WHERE id=? AND user_id=?",
                    (now, conversation_id, self.user_id),
                )

    def get_conversation(self, conversation_id: str) -> dict | None:
        with self.connect() as c:
            conversation = c.execute(
                "SELECT * FROM conversations WHERE id=? AND user_id=?",
                (conversation_id, self.user_id),
            ).fetchone()
            if not conversation:
                return None
            messages = c.execute(
                """SELECT role,content,created_at FROM conversation_messages
                   WHERE conversation_id=? AND user_id=?
                   ORDER BY id ASC""",
                (conversation_id, self.user_id),
            ).fetchall()

        return {
            "id": conversation["id"],
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
            "messages": [dict(row) for row in messages],
        }

    def list_conversations(self, limit: int = 30) -> list[dict]:
        limit = max(1, min(limit, 100))
        with self.connect() as c:
            rows = c.execute(
                """SELECT id,title,created_at,updated_at FROM conversations
                   WHERE user_id=? ORDER BY updated_at DESC LIMIT ?""",
                (self.user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        with self.connect() as c:
            result = c.execute(
                "DELETE FROM conversations WHERE id=? AND user_id=?",
                (conversation_id, self.user_id),
            )
            return result.rowcount == 1
