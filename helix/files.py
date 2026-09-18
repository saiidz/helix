"""Local text/code attachment storage and retrieval for Helix conversations."""
from __future__ import annotations

import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


MAX_FILE_CHARS = 500_000
MAX_CONTEXT_CHARS = 12_000
ALLOWED_MIME_PREFIXES = ("text/",)
ALLOWED_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/sql",
    "application/x-sh",
    "application/yaml",
    "application/x-yaml",
    "",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "that", "this", "with", "from", "have", "your", "you",
        "are", "for", "was", "were", "what", "how", "file", "files", "document",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_./#:+-]{3,}", text.lower())
        if token not in stop
    }


def is_text_type(mime_type: str) -> bool:
    value = (mime_type or "").lower().strip()
    return value.startswith(ALLOWED_MIME_PREFIXES) or value in ALLOWED_MIME_TYPES


class FileStore:
    """SQLite-backed local attachment store.

    Contents remain local application state. This is not a filesystem browser and
    cannot read arbitrary paths from the user's machine.
    """

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                content TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_attachments_conversation
                         ON attachments(conversation_id, updated_at DESC)""")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _row(row: sqlite3.Row, include_content: bool = False) -> dict:
        item = {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "name": row["name"],
            "mime_type": row["mime_type"],
            "size_bytes": int(row["size_bytes"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if include_content:
            item["content"] = row["content"]
        return item

    def add(
        self,
        conversation_id: str,
        name: str,
        content: str,
        mime_type: str = "text/plain",
    ) -> dict:
        conversation_id = conversation_id.strip()
        name = name.strip()
        content = content.replace("\x00", "")

        if not conversation_id:
            raise ValueError("Conversation id is required")
        if not name or len(name) > 255:
            raise ValueError("File name is invalid")
        if not is_text_type(mime_type):
            raise ValueError("Only text/code attachments are supported in this build")
        if not content:
            raise ValueError("File is empty")
        if len(content) > MAX_FILE_CHARS:
            raise ValueError("File is too large for the local text attachment limit")

        file_id = str(uuid.uuid4())
        now = utc_now()
        size_bytes = len(content.encode("utf-8"))

        with self.connect() as c:
            c.execute(
                """INSERT INTO attachments
                   (id,conversation_id,name,mime_type,content,size_bytes,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    file_id,
                    conversation_id,
                    name,
                    mime_type or "text/plain",
                    content,
                    size_bytes,
                    now,
                    now,
                ),
            )
            row = c.execute(
                "SELECT * FROM attachments WHERE id=?",
                (file_id,),
            ).fetchone()

        return self._row(row)

    def list(self, conversation_id: str, limit: int = 50) -> list[dict]:
        limit = max(1, min(limit, 100))
        with self.connect() as c:
            rows = c.execute(
                """SELECT * FROM attachments
                   WHERE conversation_id=?
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (conversation_id, limit),
            ).fetchall()
        return [self._row(row) for row in rows]

    def delete(self, file_id: str, conversation_id: str) -> bool:
        with self.connect() as c:
            result = c.execute(
                "DELETE FROM attachments WHERE id=? AND conversation_id=?",
                (file_id, conversation_id),
            )
            return result.rowcount == 1


    def clear_conversation(self, conversation_id: str) -> int:
        with self.connect() as c:
            count = int(
                c.execute(
                    "SELECT COUNT(*) FROM attachments WHERE conversation_id=?",
                    (conversation_id,),
                ).fetchone()[0]
            )
            c.execute(
                "DELETE FROM attachments WHERE conversation_id=?",
                (conversation_id,),
            )
        return count

    def retrieve(
        self,
        conversation_id: str,
        query: str,
        limit: int = 3,
    ) -> list[dict]:
        query_tokens = _tokens(query)

        with self.connect() as c:
            rows = c.execute(
                """SELECT * FROM attachments
                   WHERE conversation_id=?
                   ORDER BY updated_at DESC
                   LIMIT 100""",
                (conversation_id,),
            ).fetchall()

        if not rows:
            return []

        referential = bool(
            re.search(
                r"\b(this|that|attached|attachment|uploaded|file|document|code|repo)\b",
                query,
                flags=re.IGNORECASE,
            )
        )

        scored: list[tuple[float, sqlite3.Row]] = []
        for index, row in enumerate(rows):
            filename_tokens = _tokens(row["name"])
            body_tokens = _tokens(row["content"][:20_000])
            overlap = len(query_tokens & filename_tokens) * 3 + len(query_tokens & body_tokens)
            recency = max(0.0, 1.0 - index * 0.05)
            if overlap or referential:
                scored.append((overlap + recency, row))

        selected_rows = [
            row
            for _, row in sorted(scored, key=lambda item: item[0], reverse=True)[
                : max(1, min(limit, 5))
            ]
        ]

        remaining = MAX_CONTEXT_CHARS
        selected: list[dict] = []

        for row in selected_rows:
            if remaining <= 0:
                break
            excerpt = row["content"][: min(6000, remaining)]
            remaining -= len(excerpt)
            item = self._row(row)
            item["excerpt"] = excerpt
            selected.append(item)

        return selected
