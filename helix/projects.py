"""Read-only local project workspace for Helix Engineer.

Projects are explicitly imported by the user through the browser. Helix never
scans arbitrary local paths. Files are stored as local text/code snapshots and
retrieved as untrusted context.
"""
from __future__ import annotations

import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


MAX_PROJECT_FILES = 400
MAX_FILE_CHARS = 350_000
MAX_CONTEXT_CHARS = 18_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "that", "this", "with", "from", "have", "your", "you",
        "are", "for", "was", "were", "what", "how", "file", "files", "project",
        "code", "src", "app",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_./#:+-]{3,}", text.lower())
        if token not in stop
    }


def _language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".sh": "shell",
        ".ps1": "powershell",
        ".bat": "batch",
        ".cmd": "batch",
    }.get(suffix, "text")


class ProjectStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS project_files (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                path TEXT NOT NULL,
                language TEXT NOT NULL,
                content TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id,path),
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_project_files_project
                         ON project_files(project_id,path)""")

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

    def create(self, name: str) -> dict:
        name = " ".join(name.split())
        if not name or len(name) > 120:
            raise ValueError("Project name is invalid")

        project_id = str(uuid.uuid4())
        now = utc_now()

        with self.connect() as c:
            c.execute(
                "INSERT INTO projects(id,name,created_at,updated_at) VALUES (?,?,?,?)",
                (project_id, name, now, now),
            )

        return {
            "id": project_id,
            "name": name,
            "created_at": now,
            "updated_at": now,
            "file_count": 0,
        }

    def get(self, project_id: str) -> dict | None:
        with self.connect() as c:
            row = c.execute(
                """SELECT p.id,p.name,p.created_at,p.updated_at,
                          COUNT(f.id) AS file_count
                   FROM projects p
                   LEFT JOIN project_files f ON f.project_id=p.id
                   WHERE p.id=?
                   GROUP BY p.id""",
                (project_id,),
            ).fetchone()

        return dict(row) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(limit, 100))
        with self.connect() as c:
            rows = c.execute(
                """SELECT p.id,p.name,p.created_at,p.updated_at,
                          COUNT(f.id) AS file_count
                   FROM projects p
                   LEFT JOIN project_files f ON f.project_id=p.id
                   GROUP BY p.id
                   ORDER BY p.updated_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_file(self, project_id: str, path: str, content: str) -> dict:
        if self.get(project_id) is None:
            raise ValueError("Project not found")

        normalized = path.replace("\\", "/").strip("/")
        if not normalized or len(normalized) > 500:
            raise ValueError("Project file path is invalid")

        content = content.replace("\x00", "")
        if not content:
            raise ValueError("Project file is empty")
        if len(content) > MAX_FILE_CHARS:
            raise ValueError("Project file is too large")

        with self.connect() as c:
            file_count = int(
                c.execute(
                    "SELECT COUNT(*) FROM project_files WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
            )
            existing = c.execute(
                "SELECT id FROM project_files WHERE project_id=? AND path=?",
                (project_id, normalized),
            ).fetchone()

            if not existing and file_count >= MAX_PROJECT_FILES:
                raise ValueError("Project file limit reached")

            now = utc_now()
            language = _language(normalized)
            size_bytes = len(content.encode("utf-8"))

            if existing:
                file_id = existing["id"]
                c.execute(
                    """UPDATE project_files
                       SET language=?,content=?,size_bytes=?,updated_at=?
                       WHERE id=?""",
                    (language, content, size_bytes, now, file_id),
                )
            else:
                file_id = str(uuid.uuid4())
                c.execute(
                    """INSERT INTO project_files
                       (id,project_id,path,language,content,size_bytes,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        file_id,
                        project_id,
                        normalized,
                        language,
                        content,
                        size_bytes,
                        now,
                        now,
                    ),
                )

            c.execute(
                "UPDATE projects SET updated_at=? WHERE id=?",
                (now, project_id),
            )

        return {
            "id": file_id,
            "project_id": project_id,
            "path": normalized,
            "language": language,
            "size_bytes": size_bytes,
            "updated_at": now,
        }

    def list_files(self, project_id: str, limit: int = 500) -> list[dict]:
        limit = max(1, min(limit, 500))
        with self.connect() as c:
            rows = c.execute(
                """SELECT id,project_id,path,language,size_bytes,updated_at
                   FROM project_files
                   WHERE project_id=?
                   ORDER BY path ASC
                   LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def retrieve(self, project_id: str, query: str, limit: int = 6) -> list[dict]:
        query_tokens = _tokens(query)

        with self.connect() as c:
            rows = c.execute(
                """SELECT * FROM project_files
                   WHERE project_id=?
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (project_id, MAX_PROJECT_FILES),
            ).fetchall()

        if not rows:
            return []

        general_project_request = bool(
            re.search(
                r"\b(project|repo|repository|codebase|architecture|where|find|search|bug|"
                r"implement|refactor|review|explain|how does)\b",
                query,
                flags=re.IGNORECASE,
            )
        )

        scored: list[tuple[float, sqlite3.Row]] = []
        for index, row in enumerate(rows):
            path_tokens = _tokens(row["path"])
            body_tokens = _tokens(row["content"][:25_000])
            overlap = len(query_tokens & path_tokens) * 4 + len(query_tokens & body_tokens)
            priority = 0.0

            filename = Path(row["path"]).name.lower()
            if filename in {
                "readme.md",
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "cargo.toml",
                "go.mod",
                "composer.json",
            }:
                priority += 1.25

            recency = max(0.0, 0.5 - index * 0.01)

            if overlap or general_project_request:
                scored.append((overlap + priority + recency, row))

        selected_rows = [
            row
            for _, row in sorted(scored, key=lambda item: item[0], reverse=True)[
                : max(1, min(limit, 10))
            ]
        ]

        remaining = MAX_CONTEXT_CHARS
        selected: list[dict] = []

        for row in selected_rows:
            if remaining <= 0:
                break
            excerpt = row["content"][: min(5000, remaining)]
            remaining -= len(excerpt)
            selected.append(
                {
                    "id": row["id"],
                    "path": row["path"],
                    "language": row["language"],
                    "size_bytes": int(row["size_bytes"]),
                    "excerpt": excerpt,
                }
            )

        return selected

    def delete(self, project_id: str) -> bool:
        with self.connect() as c:
            result = c.execute(
                "DELETE FROM projects WHERE id=?",
                (project_id,),
            )
            return result.rowcount == 1
