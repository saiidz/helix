"""Local, explicitly selected chat -> reviewed memory. Never trains model weights."""
from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid

from .memory import MemoryStore, utc_now

# These conservative English rules are a convenience, NOT a security/PII guarantee.
# No model output, file, tool result or web page is a candidate source.
_BLOCKED = re.compile(
    r"(?i)\b(password|passphrase|secret|token|api.?key|access.?key|private.?key|"
    r"ssn|social security|credit card|bank account|address|diagnosis|medical|"
    r"health|religion|political|passport|ignore|override|bypass|execute|"
    r"system prompt|developer message|approval|permission|sudo|administrator)(?:s|es)?\b"
    r"|https?://|www\.|@|\d{6,}|-----BEGIN|\b(?:sk-|ghp_|github_pat_)",
)
_PATTERNS = (
    ("preference", re.compile(r"(?i)^I (?:prefer|like|dislike|do not like|don't like)\s+\S")),
    ("project", re.compile(r"(?i)^My (?:project|repository|codebase|app) (?:uses|is called)\s+\S")),
    ("profile", re.compile(r"(?i)^My (?:name|timezone) is\s+\S")),
)


def candidate_from_text(text: str) -> tuple[str, str] | None:
    """Keep the whole short first-person statement; never infer a new assertion."""
    text = unicodedata.normalize("NFKC", text).strip()
    if not 6 <= len(text) <= 280:
        return None
    if any(char in text for char in "\n\r\t`<>{}[]?;\""):
        return None
    if any(unicodedata.category(char).startswith("C") for char in text):
        return None
    if _BLOCKED.search(text) or re.search(r"[.!]\s+\S", text):
        return None
    for kind, pattern in _PATTERNS:
        if pattern.match(text):
            return kind, text
    return None


def _fingerprint(text: str) -> str:
    normalized = " ".join(text.casefold().rstrip(".!").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ChatLearning:
    """Review queue in the existing owner-scoped SQLite database.

    Opt-in alone does not scan history. The owner must select a conversation and
    request a review. Only a second, explicit approval writes a usable memory.
    """

    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.user_id = memory.user_id
        with memory.connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS chat_learning_settings (
                user_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS chat_learning_candidates (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                source_message_id INTEGER NOT NULL,
                kind TEXT NOT NULL, content TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','forgotten')),
                memory_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(user_id, fingerprint),
                FOREIGN KEY(source_message_id) REFERENCES conversation_messages(id) ON DELETE CASCADE
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_chat_learning_owner
                ON chat_learning_candidates(user_id, status, created_at)""")
            # Source deletion and 'Forget' remove this feature's derived memory,
            # but never a manual memory independently re-saved by the owner.
            c.execute("""CREATE TRIGGER IF NOT EXISTS chat_learning_delete_derived
                AFTER DELETE ON chat_learning_candidates BEGIN
                DELETE FROM memories WHERE id=OLD.memory_id AND user_id=OLD.user_id
                    AND source='reviewed_chat';
                END""")
            c.execute("""CREATE TRIGGER IF NOT EXISTS chat_learning_memory_deactivated
                AFTER UPDATE OF active ON memories WHEN NEW.active=0 BEGIN
                UPDATE chat_learning_candidates SET status='forgotten', content='', memory_id=NULL
                    WHERE memory_id=NEW.id AND user_id=NEW.user_id;
                END""")
            c.execute("""CREATE TRIGGER IF NOT EXISTS chat_learning_memory_deleted
                AFTER DELETE ON memories BEGIN
                UPDATE chat_learning_candidates SET status='forgotten', content='', memory_id=NULL
                    WHERE memory_id=OLD.id AND user_id=OLD.user_id;
                END""")

    def _enabled(self, c) -> bool:
        row = c.execute("SELECT enabled FROM chat_learning_settings WHERE user_id=?",
                        (self.user_id,)).fetchone()
        return bool(row and row["enabled"])

    def settings(self) -> dict:
        with self.memory.connect() as c:
            enabled = self._enabled(c)
        return {"enabled": enabled, "mode": "selected_chat_review",
                "training_enabled": False, "external_calls": False}

    def set_enabled(self, enabled: bool) -> dict:
        if type(enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        with self.memory.connect() as c:
            c.execute("""INSERT INTO chat_learning_settings VALUES (?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,
                updated_at=excluded.updated_at""", (self.user_id, int(enabled), utc_now()))
        return self.settings()

    def review_conversation(self, conversation_id: str) -> dict:
        """Explicit selection is permission to inspect up to 100 recent user turns."""
        with self.memory.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if not self._enabled(c):
                raise PermissionError("Enable reviewed chat learning first")
            owner = c.execute("SELECT id FROM conversations WHERE id=? AND user_id=?",
                              (conversation_id, self.user_id)).fetchone()
            if owner is None:
                raise LookupError("Conversation not found")
            rows = c.execute("""SELECT id,substr(content,1,281) AS content FROM conversation_messages
                WHERE conversation_id=? AND user_id=? AND role='user'
                ORDER BY id DESC LIMIT 100""", (conversation_id, self.user_id)).fetchall()
            total = c.execute("SELECT count(*) FROM chat_learning_candidates WHERE user_id=?",
                              (self.user_id,)).fetchone()[0]
            added = 0
            for row in rows:
                candidate = candidate_from_text(row["content"])
                if not candidate or total >= 500:
                    continue
                kind, content = candidate
                duplicate = c.execute("""SELECT id FROM memories
                    WHERE user_id=? AND active=1 AND lower(content)=lower(?)""",
                                      (self.user_id, content)).fetchone()
                if duplicate:
                    continue
                now = utc_now()
                inserted = c.execute("""INSERT INTO chat_learning_candidates
                    (id,user_id,source_message_id,kind,content,fingerprint,status,memory_id,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,'pending',NULL,?,?)
                    ON CONFLICT(user_id,fingerprint) DO NOTHING""",
                    (str(uuid.uuid4()), self.user_id, row["id"], kind, content,
                     _fingerprint(content), now, now)).rowcount
                added += inserted
                total += inserted
            return {"messages_considered": len(rows), "suggestions_added": added,
                    "limit_reached": total >= 500}

    def list_candidates(self) -> list[dict]:
        with self.memory.connect() as c:
            rows = c.execute("""SELECT q.id,q.kind,q.content,q.status,q.memory_id,
                    q.created_at,q.updated_at,m.conversation_id,m.created_at AS source_created_at
                FROM chat_learning_candidates q
                JOIN conversation_messages m ON m.id=q.source_message_id AND m.user_id=q.user_id
                JOIN conversations v ON v.id=m.conversation_id AND v.user_id=q.user_id
                WHERE q.user_id=? AND q.status IN ('pending','approved')
                ORDER BY q.created_at DESC LIMIT 500""", (self.user_id,)).fetchall()
        return [dict(row) for row in rows]

    def approve(self, candidate_id: str, content: str | None = None) -> dict:
        with self.memory.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if not self._enabled(c):
                raise PermissionError("Learning is off; approval is disabled")
            row = c.execute("""SELECT q.* FROM chat_learning_candidates q
                JOIN conversation_messages m ON m.id=q.source_message_id AND m.user_id=q.user_id
                JOIN conversations v ON v.id=m.conversation_id AND v.user_id=q.user_id
                WHERE q.id=? AND q.user_id=?""", (candidate_id, self.user_id)).fetchone()
            if row is None:
                raise LookupError("Suggestion not found")
            if row["status"] != "pending":
                raise ValueError("Only pending suggestions can be approved")
            candidate = candidate_from_text(row["content"] if content is None else content)
            if candidate is None:
                raise ValueError("Use one short first-person preference, project note, name or timezone; exclude sensitive details")
            kind, reviewed = candidate
            duplicate = c.execute("""SELECT id FROM memories
                WHERE user_id=? AND active=1 AND lower(content)=lower(?)""",
                                  (self.user_id, reviewed)).fetchone()
            if duplicate:
                raise ValueError("That memory already exists; dismiss this suggestion")
            now, memory_id = utc_now(), str(uuid.uuid4())
            c.execute("""INSERT INTO memories
                (id,user_id,kind,content,source,pinned,importance,active,created_at,updated_at,last_used_at)
                VALUES (?,?,?,?,'reviewed_chat',0,0.7,1,?,?,NULL)""",
                (memory_id, self.user_id, kind, reviewed, now, now))
            c.execute("""UPDATE chat_learning_candidates
                SET status='approved',content=?,kind=?,memory_id=?,updated_at=?
                WHERE id=? AND user_id=?""", (reviewed, kind, memory_id, now, candidate_id, self.user_id))
            return {"id": memory_id, "content": reviewed, "kind": kind, "source": "reviewed_chat"}

    def dismiss(self, candidate_id: str) -> None:
        with self.memory.connect() as c:
            result = c.execute("""UPDATE chat_learning_candidates
                SET status='rejected',content='',updated_at=?
                WHERE id=? AND user_id=? AND status='pending'""",
                (utc_now(), candidate_id, self.user_id))
            if result.rowcount != 1:
                raise LookupError("Pending suggestion not found")

    def forget(self, candidate_id: str) -> None:
        with self.memory.connect() as c:
            result = c.execute("DELETE FROM chat_learning_candidates WHERE id=? AND user_id=?",
                               (candidate_id, self.user_id))
            if result.rowcount != 1:
                raise LookupError("Suggestion not found")

    def clear(self) -> None:
        """Remove this feature's rows and derived memories; leave chat history intact."""
        with self.memory.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("DELETE FROM chat_learning_candidates WHERE user_id=?", (self.user_id,))
            c.execute("DELETE FROM chat_learning_settings WHERE user_id=?", (self.user_id,))

    def export(self) -> dict:
        return {"schema_version": 1, "settings": self.settings(),
                "items": self.list_candidates(),
                "notice": "Personal memory export, not a training dataset. Contains private information."}
