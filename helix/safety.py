"""Persistent fail-closed Emergency Lockdown for HELIX Engineer actions.

The safety database lives outside the selected workspace by default. Locking is
non-interactive so a separate local script can disable new actions even when the
UI is unavailable. Reset intentionally requires an interactive terminal; there
is no HTTP unlock endpoint.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, TextIO


class SafetyError(RuntimeError):
    pass


def default_safety_path() -> Path:
    return Path.home() / ".helix" / "safety.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SafetyStore:
    def __init__(self, path: Path | None = None):
        self.path = (path or default_safety_path()).expanduser().resolve()
        self.initialization_error: str | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as c:
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("""CREATE TABLE IF NOT EXISTS safety_state (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    locked INTEGER NOT NULL CHECK(locked IN (0,1)),
                    generation INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""")
                c.execute(
                    """INSERT OR IGNORE INTO safety_state
                       (id,locked,generation,reason,updated_at)
                       VALUES (1,0,0,'',?)""",
                    (utc_now(),),
                )
            try:
                self.path.chmod(0o600)
            except OSError:
                pass
        except (OSError, sqlite3.Error) as exc:
            self.initialization_error = f"{type(exc).__name__}: {exc}"

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def status(self) -> dict:
        if self.initialization_error:
            return {
                "locked": True,
                "generation": -1,
                "reason": "Safety state unavailable; Engineer actions fail closed",
                "updated_at": None,
                "fail_closed": True,
            }
        try:
            with self.connect() as c:
                row = c.execute(
                    "SELECT locked,generation,reason,updated_at FROM safety_state WHERE id=1"
                ).fetchone()
            if row is None:
                raise sqlite3.DatabaseError("missing safety state")
            return {
                "locked": bool(row["locked"]),
                "generation": int(row["generation"]),
                "reason": row["reason"],
                "updated_at": row["updated_at"],
                "fail_closed": False,
            }
        except (OSError, sqlite3.Error):
            return {
                "locked": True,
                "generation": -1,
                "reason": "Safety state unreadable; Engineer actions fail closed",
                "updated_at": None,
                "fail_closed": True,
            }

    def is_locked(self) -> bool:
        return self.status()["locked"] is True

    def lock(self, reason: str = "Owner emergency switch") -> dict:
        if self.initialization_error:
            raise SafetyError("Safety state is unavailable; Engineer already fails closed")
        reason = " ".join(str(reason).split())[:500] or "Owner emergency switch"
        try:
            with self.connect() as c:
                c.execute("BEGIN IMMEDIATE")
                row = c.execute(
                    "SELECT generation FROM safety_state WHERE id=1"
                ).fetchone()
                if row is None:
                    raise sqlite3.DatabaseError("missing safety state")
                c.execute(
                    """UPDATE safety_state
                       SET locked=1,generation=?,reason=?,updated_at=?
                       WHERE id=1""",
                    (int(row["generation"]) + 1, reason, utc_now()),
                )
        except sqlite3.Error as exc:
            raise SafetyError("Could not persist Emergency Lockdown") from exc
        return self.status()

    def unlock_interactive(
        self,
        *,
        stream: TextIO | None = None,
        input_fn: Callable[[str], str] | None = None,
    ) -> dict:
        stream = stream or sys.stdin
        input_fn = input_fn or input
        if not stream.isatty():
            raise SafetyError(
                "Reset requires an interactive local terminal; unattended reset is disabled"
            )
        state = self.status()
        if state["fail_closed"]:
            raise SafetyError("Safety state is unavailable; repair it manually before reset")
        if not state["locked"]:
            return state
        phrase = f"RESET HELIX LOCKDOWN {state['generation']}"
        response = input_fn(
            "Emergency Lockdown is active.\n"
            f"Type {phrase} exactly to restore reviewed Engineer actions: "
        )
        if response.strip() != phrase:
            raise SafetyError("Reset phrase did not match; lockdown remains active")
        try:
            with self.connect() as c:
                c.execute("BEGIN IMMEDIATE")
                current = c.execute(
                    "SELECT generation,locked FROM safety_state WHERE id=1"
                ).fetchone()
                if current is None or not current["locked"]:
                    raise SafetyError("Safety state changed during reset; inspect status first")
                if int(current["generation"]) != int(state["generation"]):
                    raise SafetyError("Lockdown generation changed; rerun reset")
                c.execute(
                    """UPDATE safety_state
                       SET locked=0,reason='Owner reset from interactive terminal',updated_at=?
                       WHERE id=1""",
                    (utc_now(),),
                )
        except sqlite3.Error as exc:
            raise SafetyError("Could not reset Emergency Lockdown") from exc
        return self.status()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HELIX Engineer Emergency Lockdown control")
    parser.add_argument("--path", type=Path, default=default_safety_path())
    sub = parser.add_subparsers(dest="command", required=True)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("--reason", default="Owner emergency switch")
    sub.add_parser("status")
    sub.add_parser("unlock")
    args = parser.parse_args(argv)
    store = SafetyStore(args.path)
    try:
        if args.command == "lock":
            state = store.lock(args.reason)
        elif args.command == "unlock":
            state = store.unlock_interactive()
        else:
            state = store.status()
        print(json.dumps(state, indent=2))
        return 0
    except SafetyError as exc:
        print(f"HELIX safety: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
