"""Local provenance-preserving knowledge cache learned from explicit web research."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from .freshness import cache_metadata, requires_live_evidence

if TYPE_CHECKING:
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
    """SQLite-backed research cache; never a model-training or freshness claim."""

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
                is_page = bool(doc and doc.text.strip())
                content = (doc.text if is_page else result.snippet).strip()
                if not content:
                    continue
                title = (doc.title if is_page and doc.title else result.title).strip() or result.url
                content = content[:12000]
                source_type = "page" if is_page else "snippet"
                previous = c.execute(
                    "SELECT content,title,source_type FROM web_knowledge WHERE url=?",
                    (result.url,),
                ).fetchone()
                # A failed page fetch must not overwrite stronger evidence with a
                # search snippet or renew the old page's retrieval timestamp.
                if previous and previous["source_type"] == "page" and not is_page:
                    continue
                # The web adapter has a five-minute cache without fetch timestamps.
                # Do not pretend an identical cached result was freshly verified.
                # Conservatively keep its original date even if a real fetch was
                # identical. A future timestamped adapter can prove revalidation.
                if previous and all((previous["content"] == content,
                                     previous["title"] == title[:300],
                                     previous["source_type"] == source_type)):
                    continue
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
                    (result.url, title[:300], content, query[:500], source_type, now, now),
                )
                learned += 1
        return learned

    def retrieve(self, query: str, limit: int = 4) -> list[dict]:
        if requires_live_evidence(query) or limit <= 0:
            return []
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        with self.connect() as c:
            rows = c.execute(
                """SELECT url,title,content,query,source_type,updated_at,last_used_at
                   FROM web_knowledge ORDER BY updated_at DESC LIMIT 250"""
            ).fetchall()
        now = datetime.now(timezone.utc)
        scored: list[tuple[int, dict]] = []
        for row in rows:
            metadata = cache_metadata(row["updated_at"], row["source_type"], now)
            if metadata["cache_status"] != "eligible":
                continue
            corpus_tokens = _tokens(f"{row['title']} {row['query']} {row['content'][:4000]}")
            overlap = len(query_tokens & corpus_tokens)
            if overlap:
                item = dict(row)
                item.update(metadata)
                scored.append((overlap, item))
        selected = [item for _, item in sorted(
            scored, key=lambda pair: (pair[0], pair[1]["updated_at"]), reverse=True,
        )[:min(limit, 8)]]
        if selected:
            urls = [item["url"] for item in selected]
            placeholders = ",".join("?" for _ in urls)
            with self.connect() as c:
                c.execute(
                    f"UPDATE web_knowledge SET last_used_at=? WHERE url IN ({placeholders})",
                    (utc_now(), *urls),
                )
        return selected

    def list_entries(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        with self.connect() as c:
            rows = c.execute(
                """SELECT url,title,query,source_type,created_at,updated_at,last_used_at
                   FROM web_knowledge ORDER BY updated_at DESC LIMIT ?""", (limit,),
            ).fetchall()
        now = datetime.now(timezone.utc)
        return [dict(row, **cache_metadata(row["updated_at"], row["source_type"], now))
                for row in rows]

    def clear(self) -> int:
        with self.connect() as c:
            count = int(c.execute("SELECT COUNT(*) FROM web_knowledge").fetchone()[0])
            c.execute("DELETE FROM web_knowledge")
        return count

    def count(self) -> int:
        with self.connect() as c:
            return int(c.execute("SELECT COUNT(*) FROM web_knowledge").fetchone()[0])
