"""Local provenance-preserving knowledge cache learned from explicit web research."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .web import SearchResult, WebDocument


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    stop = {"the","and","that","this","with","from","have","your","you","are","for","was","were","what","how"}
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_'-]{3,}", text.lower())
        if token not in stop
    }


class KnowledgeStore:
    """SQLite-backed cache of web knowledge with source provenance."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS web_knowledge (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                query TEXT NOT NULL,
                source_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_web_knowledge_updated
                         ON web_knowledge(updated_at DESC)""")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def learn(
        self,
        query: str,
        results: list[SearchResult],
        documents: list[WebDocument],
    ) -> int:
        docs = {doc.url: doc for doc in documents}
        now = utc_now()
        learned = 0

        with self.connect() as c:
            for result in results[:8]:
                doc = docs.get(result.url)
                content = (doc.text if doc and doc.text else result.snippet).strip()
                if not content:
                    continue

                title = (doc.title if doc and doc.title else result.title).strip() or result.url
                content = content[:12000]

                c.execute(
                    """INSERT INTO web_knowledge
                       (url,title,content,query,source_type,created_at,updated_at,last_used_at)
                       VALUES (?,?,?,?,?,?,?,NULL)
                       ON CONFLICT(url) DO UPDATE SET
                         title=excluded.title,
                         content=excluded.content,
                         query=excluded.query,
                         source_type=excluded.source_type,
                         updated_at=excluded.updated_at""",
                    (
                        result.url,
                        title[:300],
                        content,
                        query[:500],
                        "web",
                        now,
                        now,
                    ),
                )
                learned += 1

        return learned

    def retrieve(self, query: str, limit: int = 4) -> list[dict]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        with self.connect() as c:
            rows = c.execute(
                """SELECT url,title,content,query,updated_at,last_used_at
                   FROM web_knowledge
                   ORDER BY updated_at DESC
                   LIMIT 250"""
            ).fetchall()

        scored: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            corpus_tokens = _tokens(
                f"{row['title']} {row['query']} {row['content'][:4000]}"
            )
            overlap = len(query_tokens & corpus_tokens)
            if overlap:
                scored.append((overlap, row))

        selected = [
            row for _, row in sorted(
                scored,
                key=lambda item: (item[0], item[1]["updated_at"]),
                reverse=True,
            )[: max(1, min(limit, 8))]
        ]

        if selected:
            now = utc_now()
            urls = [row["url"] for row in selected]
            placeholders = ",".join("?" for _ in urls)
            with self.connect() as c:
                c.execute(
                    f"UPDATE web_knowledge SET last_used_at=? WHERE url IN ({placeholders})",
                    (now, *urls),
                )

        return [
            {
                "url": row["url"],
                "title": row["title"],
                "content": row["content"],
                "query": row["query"],
                "updated_at": row["updated_at"],
            }
            for row in selected
        ]

    def list_entries(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        with self.connect() as c:
            rows = c.execute(
                """SELECT url,title,query,created_at,updated_at,last_used_at
                   FROM web_knowledge
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear(self) -> int:
        with self.connect() as c:
            count = int(c.execute("SELECT COUNT(*) FROM web_knowledge").fetchone()[0])
            c.execute("DELETE FROM web_knowledge")
        return count

    def count(self) -> int:
        with self.connect() as c:
            return int(c.execute("SELECT COUNT(*) FROM web_knowledge").fetchone()[0])
