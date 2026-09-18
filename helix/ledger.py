"""Atomic spending reservations. Prompt/answer text is never stored in this ledger."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from typing import Iterator
from datetime import datetime, timezone
from pathlib import Path


class LedgerError(Exception):
    pass


class BudgetExceeded(LedgerError):
    pass


class DuplicateRequest(LedgerError):
    pass


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                month TEXT NOT NULL, role TEXT NOT NULL, model_id TEXT NOT NULL,
                reserved INTEGER NOT NULL, charged INTEGER NOT NULL,
                status TEXT NOT NULL, usage_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL)""")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def reserve(self, request_id: str, fingerprint: str, role: str, model_id: str,
                amount: int, monthly_limit: int):
        if amount < 0 or monthly_limit < 0:
            raise ValueError("Negative reservation or limit")
        month = self.month()
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            existing = c.execute("SELECT fingerprint,status FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise DuplicateRequest("Idempotency key belongs to a different request")
                raise DuplicateRequest("Request already recorded; no duplicate provider call was made")
            spent = c.execute("SELECT COALESCE(SUM(charged),0) FROM requests WHERE month=?", (month,)).fetchone()[0]
            if spent + amount > monthly_limit:
                raise BudgetExceeded("Monthly model-cost budget exhausted")
            c.execute("INSERT INTO requests VALUES (?,?,?,?,?,?,?,?,?,?)", (
                request_id, fingerprint, month, role, model_id, amount, amount,
                "reserved", 0, datetime.now(timezone.utc).isoformat()))

    def finish(self, request_id: str, actual: int | None):
        if actual is not None and actual < 0:
            raise ValueError("Negative actual cost")
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT reserved,status FROM requests WHERE request_id=?", (request_id,)).fetchone()
            if not row or row[1] != "reserved":
                raise LedgerError("Only an active reservation can be finished")
            charged = row[0] if actual is None else actual
            # Record real overages rather than falsifying costs to fit a cap.
            status = "completed_over_estimate" if charged > row[0] else "completed"
            c.execute("UPDATE requests SET charged=?,status=?,usage_verified=? WHERE request_id=?",
                      (charged, status, int(actual is not None), request_id))

    def hold_uncertain_failure(self, request_id: str):
        # A timeout can still be billable. Keep its reservation; no blind paid retry.
        with self.connect() as c:
            c.execute("UPDATE requests SET status='failed_cost_uncertain' WHERE request_id=? AND status='reserved'", (request_id,))

    def summary(self) -> dict:
        with self.connect() as c:
            rows = c.execute("SELECT status,COUNT(*),COALESCE(SUM(charged),0) FROM requests WHERE month=? GROUP BY status", (self.month(),)).fetchall()
        return {"month": self.month(), "model_cost_usd": sum(r[2] for r in rows) / 1000000,
                "counts": {r[0]: r[1] for r in rows},
                "scope": "single-owner prototype; excludes hosting, tools, speech and other business costs"}
