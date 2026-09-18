"""Local task list for Helix Companion.

Tasks are application state, not OS/calendar reminders. This module intentionally
does not claim notification delivery. A later connector can add scheduling.
"""
from __future__ import annotations

import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                due_at TEXT,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_tasks_status_due
                         ON tasks(status,due_at,updated_at DESC)""")

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
    def _row(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "details": row["details"],
            "due_at": row["due_at"],
            "status": row["status"],
            "source": row["source"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
        }

    def add(
        self,
        title: str,
        details: str = "",
        due_at: str | None = None,
        source: str = "user",
    ) -> dict:
        title = " ".join(title.split())
        details = details.strip()

        if not title or len(title) > 300:
            raise ValueError("Task title is invalid")
        if len(details) > 4000:
            raise ValueError("Task details are too long")
        if due_at is not None and len(due_at) > 64:
            raise ValueError("Task due time is invalid")

        task_id = str(uuid.uuid4())
        now = utc_now()

        with self.connect() as c:
            c.execute(
                """INSERT INTO tasks
                   (id,title,details,due_at,status,source,created_at,updated_at,completed_at)
                   VALUES (?,?,?,?,?,?,?,?,NULL)""",
                (
                    task_id,
                    title,
                    details,
                    due_at,
                    "open",
                    source,
                    now,
                    now,
                ),
            )
            row = c.execute(
                "SELECT * FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()

        return self._row(row)

    def list(self, status: str = "open", limit: int = 100) -> list[dict]:
        if status not in {"open", "done", "all"}:
            raise ValueError("Unsupported task status")

        limit = max(1, min(limit, 500))
        query = """SELECT * FROM tasks"""
        params: list[object] = []

        if status != "all":
            query += " WHERE status=?"
            params.append(status)

        query += """
            ORDER BY
              CASE WHEN due_at IS NULL OR due_at='' THEN 1 ELSE 0 END,
              due_at ASC,
              updated_at DESC
            LIMIT ?
        """
        params.append(limit)

        with self.connect() as c:
            rows = c.execute(query, params).fetchall()

        return [self._row(row) for row in rows]

    def set_done(self, task_id: str, done: bool) -> dict | None:
        now = utc_now()
        with self.connect() as c:
            result = c.execute(
                """UPDATE tasks
                   SET status=?, updated_at=?, completed_at=?
                   WHERE id=?""",
                (
                    "done" if done else "open",
                    now,
                    now if done else None,
                    task_id,
                ),
            )
            if result.rowcount != 1:
                return None
            row = c.execute(
                "SELECT * FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()

        return self._row(row)

    def delete(self, task_id: str) -> bool:
        with self.connect() as c:
            result = c.execute(
                "DELETE FROM tasks WHERE id=?",
                (task_id,),
            )
            return result.rowcount == 1

    def capture_explicit(self, text: str) -> dict | None:
        """Capture explicit task-list requests without promising a notification."""
        patterns = (
            r"^\s*add (?:a )?task(?: to)?\s+(.+?)\s*$",
            r"^\s*add (.+?) to my task list\s*$",
            r"^\s*put (.+?) on my task list\s*$",
        )

        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip(" .")
                if title:
                    with self.connect() as c:
                        existing = c.execute(
                            """SELECT * FROM tasks
                               WHERE status='open' AND lower(title)=lower(?)
                               ORDER BY updated_at DESC LIMIT 1""",
                            (title,),
                        ).fetchone()
                    if existing:
                        return self._row(existing)
                    return self.add(title, source="explicit_chat")

        return None
