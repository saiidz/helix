"""Durable local metadata for Engineer jobs.

This store persists task status, bounded event history and final receipts so the
main HELIX UI can survive refresh/restart without pretending an interrupted
process is still running. It does not resume commands after process restart.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


MAX_EVENT_JSON = 24_000
MAX_TASK = 6_000
INFLIGHT = {"queued", "running", "waiting_for_approval", "stopping"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EngineerJobStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS engineer_jobs (
                id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                workspace TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result_json TEXT,
                receipt_count INTEGER NOT NULL DEFAULT 0
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS engineer_job_events (
                job_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                kind TEXT NOT NULL,
                value_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(job_id, seq),
                FOREIGN KEY(job_id) REFERENCES engineer_jobs(id) ON DELETE CASCADE
            )""")
            c.execute("""CREATE INDEX IF NOT EXISTS idx_engineer_jobs_updated
                         ON engineer_jobs(updated_at DESC)""")
            placeholders = ",".join("?" for _ in INFLIGHT)
            c.execute(
                f"""UPDATE engineer_jobs
                    SET status='interrupted',updated_at=?
                    WHERE status IN ({placeholders})""",
                (utc_now(), *sorted(INFLIGHT)),
            )

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

    def create(self, task: str, workspace: str) -> dict:
        task = task.strip()
        if not task or len(task.encode("utf-8")) > MAX_TASK:
            raise ValueError("Engineer task is empty or too large")
        if not workspace:
            raise ValueError("Engineer workspace is required")
        job_id = uuid.uuid4().hex
        now = utc_now()
        with self.connect() as c:
            c.execute(
                """INSERT INTO engineer_jobs
                   (id,task,workspace,status,created_at,updated_at,result_json,receipt_count)
                   VALUES (?,?,?,?,?,?,NULL,0)""",
                (job_id, task, workspace, "queued", now, now),
            )
        return self.get(job_id)

    def set_status(self, job_id: str, status: str) -> None:
        if not status or len(status) > 64:
            raise ValueError("Invalid Engineer job status")
        with self.connect() as c:
            result = c.execute(
                "UPDATE engineer_jobs SET status=?,updated_at=? WHERE id=?",
                (status, utc_now(), job_id),
            )
            if result.rowcount != 1:
                raise LookupError("Engineer job not found")

    def append_event(self, job_id: str, seq: int, kind: str, value) -> None:
        if type(seq) is not int or seq < 1 or not kind or len(kind) > 80:
            raise ValueError("Invalid Engineer event")
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_EVENT_JSON:
            encoded = json.dumps(
                {"truncated": True, "excerpt": encoded[:8000]},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        now = utc_now()
        with self.connect() as c:
            c.execute(
                """INSERT INTO engineer_job_events(job_id,seq,kind,value_json,created_at)
                   VALUES (?,?,?,?,?)""",
                (job_id, seq, kind, encoded, now),
            )
            c.execute(
                "UPDATE engineer_jobs SET updated_at=? WHERE id=?",
                (now, job_id),
            )

    def finish(self, job_id: str, status: str, result: dict, receipt_count: int) -> None:
        if type(receipt_count) is not int or receipt_count < 0:
            raise ValueError("Invalid receipt count")
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 64_000:
            encoded = json.dumps(
                {"status": result.get("status"), "truncated": True},
                separators=(",", ":"),
            )
        with self.connect() as c:
            updated = c.execute(
                """UPDATE engineer_jobs
                   SET status=?,updated_at=?,result_json=?,receipt_count=?
                   WHERE id=?""",
                (status, utc_now(), encoded, receipt_count, job_id),
            )
            if updated.rowcount != 1:
                raise LookupError("Engineer job not found")

    def _job(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        raw = item.pop("result_json")
        item["result"] = json.loads(raw) if raw else None
        return item

    def get(self, job_id: str, event_limit: int = 200) -> dict | None:
        event_limit = max(1, min(int(event_limit), 500))
        with self.connect() as c:
            row = c.execute(
                """SELECT id,task,workspace,status,created_at,updated_at,
                          result_json,receipt_count
                   FROM engineer_jobs WHERE id=?""",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            events = c.execute(
                """SELECT seq,kind,value_json,created_at
                   FROM engineer_job_events
                   WHERE job_id=? ORDER BY seq ASC LIMIT ?""",
                (job_id, event_limit),
            ).fetchall()
        item = self._job(row)
        item["events"] = [
            {
                "seq": int(event["seq"]),
                "kind": event["kind"],
                "value": json.loads(event["value_json"]),
                "created_at": event["created_at"],
            }
            for event in events
        ]
        return item

    def list(self, limit: int = 30) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        with self.connect() as c:
            rows = c.execute(
                """SELECT id,task,workspace,status,created_at,updated_at,
                          result_json,receipt_count
                   FROM engineer_jobs
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            item = self._job(row)
            item.pop("result", None)
            items.append(item)
        return items
