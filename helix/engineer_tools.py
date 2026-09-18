"""Explicitly approved local engineering tools. This is NOT an OS sandbox.

Reads/edits are scoped to one operator-selected directory. Every command needs
approval and can act with the full privileges/network access of the host user.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Callable

MAX_FILE = 350_000
MAX_OUTPUT = 32_000
SKIP_DIRS = {".git", ".helix", ".venv", "venv", "node_modules", "__pycache__",
             ".ssh", ".aws", ".azure", ".config", "dist", "build", ".next"}
SECRET_NAMES = {".npmrc", ".pypirc", "credentials", "credentials.json", "secrets.json",
                "local.json", "id_rsa", "id_ed25519", "authorized_keys"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db"}
RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)
Approval = Callable[[str, str], bool]


class ToolError(ValueError):
    """Expected, user-readable refusal or invalid tool request."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def visible(text: str) -> str:
    """Prevent terminal control sequences from concealing approval content."""
    return "".join(c if (c in "\n\t" or c.isprintable()) else f"\\u{ord(c):04x}" for c in text)


def text(value, maximum=MAX_FILE, empty=True) -> str:
    if not isinstance(value, str) or len(value.encode("utf-8")) > maximum or (not empty and not value):
        raise ToolError("Invalid or oversized text value")
    if "\x00" in value:
        raise ToolError("NUL characters are not supported")
    return value


def integer(value, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ToolError(f"Expected an integer between {low} and {high}")
    return value


class Workspace:
    def __init__(self, root: Path, history: Path, approve: Approval,
                 cancel: threading.Event | None = None):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir() or self.root == Path(self.root.anchor) or self.root == Path.home().resolve():
            raise ToolError("Select a project directory, not an entire drive or your home directory")
        self.history = history.resolve()
        # Backups must not be discoverable as repository source files.
        if self.history == self.root or self.history.is_relative_to(self.root):
            raise ToolError("History must be outside the selected workspace")
        self.approve = approve
        self.cancel = cancel if cancel is not None else threading.Event()
        self.receipts: list[dict] = []
        self._denied: set[str] = set()

    def path(self, name: str) -> Path:
        name = text(name, 500, empty=False).replace("\\", "/")
        parts = name.split("/")
        if len(parts) > 32 or any(not p or p in {".", ".."} or p[-1:] in {".", " "}
                                  or any(c in p for c in ':<>"|?*') or RESERVED.match(p)
                                  or any(ord(c) < 32 for c in p) for p in parts):
            raise ToolError("Unsafe or unsupported relative path")
        if PurePosixPath(name).is_absolute():
            raise ToolError("Only workspace-relative paths are supported")
        lower = [p.casefold() for p in parts]
        if any(p in SKIP_DIRS for p in lower) or lower[-1] in SECRET_NAMES:
            raise ToolError("Private/generated path is excluded")
        if any(p == ".env" or p.startswith(".env.") for p in lower) or Path(lower[-1]).suffix in SECRET_SUFFIXES:
            raise ToolError("Potential credentials/private runtime file is excluded")
        candidate = self.root
        for part in parts:
            candidate = candidate / part
            if candidate.exists() or candidate.is_symlink():
                info = candidate.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise ToolError("Symlinks, junctions and reparse points are excluded")
                if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                    raise ToolError("Hard-linked files are excluded")
        if not candidate.resolve().is_relative_to(self.root):
            raise ToolError("Path escapes the workspace")
        return candidate

    def _read(self, name: str) -> bytes:
        path = self.path(name)
        if not path.is_file() or path.stat().st_size > MAX_FILE:
            raise ToolError("Expected a regular text file of at most 350,000 bytes")
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if len(raw) > MAX_FILE or b"\0" in raw:
            raise ToolError("Binary or oversized file is unsupported")
        try:
            raw.decode("utf-8")
        except UnicodeError as exc:
            raise ToolError("File is not UTF-8 text") from exc
        return raw

    def list_files(self, limit=500) -> dict:
        integer(limit, 1, 2000)
        files, visited = [], 0
        for folder, dirs, names in os.walk(self.root, followlinks=False):
            if self.cancel.is_set():
                raise ToolError("Stopped")
            visited += len(dirs) + len(names)
            keep = []
            for name in sorted(dirs):
                rel = (Path(folder) / name).relative_to(self.root).as_posix()
                try:
                    self.path(rel)
                    if len(Path(rel).parts) < 24:
                        keep.append(name)
                except (OSError, ToolError):
                    pass
            dirs[:] = keep
            for name in sorted(names):
                rel = (Path(folder) / name).relative_to(self.root).as_posix()
                try:
                    target = self.path(rel)
                    if target.is_file() and target.stat().st_size <= MAX_FILE:
                        files.append(rel)
                except (OSError, ToolError):
                    continue
                if len(files) >= limit:
                    return {"files": files, "truncated": True}
            if visited >= 20000:
                return {"files": files, "truncated": True}
        return {"files": files, "truncated": False}

    def read_file(self, path: str, offset=0, limit=6000) -> dict:
        integer(offset, 0, MAX_FILE)
        integer(limit, 1, 12000)
        raw = self._read(path)
        content = raw.decode("utf-8")
        return {"path": path, "sha256": digest(raw), "offset": offset,
                "text": content[offset:offset + limit], "characters": len(content),
                "next_offset": offset + limit if offset + limit < len(content) else None}

    def search(self, query: str) -> dict:
        text(query, 300, empty=False)
        listing = self.list_files(2000)
        results, scanned = [], 0
        for path in listing["files"]:
            if self.cancel.is_set():
                raise ToolError("Stopped")
            try:
                raw = self._read(path)
            except (OSError, ToolError):
                continue
            scanned += len(raw)
            for line, content in enumerate(raw.decode("utf-8").splitlines(), 1):
                if query.casefold() in content.casefold():
                    results.append({"path": path, "line": line, "text": content[:300]})
                    if len(results) >= 30:
                        return {"matches": results, "truncated": True}
            if scanned > 8_000_000:
                return {"matches": results, "truncated": True}
        return {"matches": results, "truncated": listing["truncated"]}

    def _permission(self, kind: str, preview: str) -> bool:
        fingerprint = digest((kind + preview).encode())
        if self.cancel.is_set() or fingerprint in self._denied:
            return False
        allowed = self.approve(kind, visible(preview)) is True
        if not allowed:
            self._denied.add(fingerprint)
        return allowed and not self.cancel.is_set()

    def edit(self, changes: list[dict]) -> dict:
        if not isinstance(changes, list) or not 1 <= len(changes) <= 8:
            raise ToolError("Provide 1 to 8 changes, one per file")
        prepared, seen, previews = [], set(), []
        for item in changes:
            if not isinstance(item, dict) or set(item) != {"path", "sha256", "old", "new"}:
                raise ToolError("Each change requires path, sha256, old and new")
            name = text(item["path"], 500, empty=False)
            target = self.path(name)
            identity = str(target).casefold()
            if identity in seen:
                raise ToolError("Only one replacement per file is allowed in a change set")
            seen.add(identity)
            old, new = text(item["old"]), text(item["new"])
            before = self._read(name) if target.exists() else None
            if before is None:
                if item["sha256"] is not None or old != "" or not target.parent.is_dir():
                    raise ToolError("New files require sha256=null, old='' and an existing parent directory")
                after = new.encode("utf-8")
            else:
                if item["sha256"] != digest(before):
                    raise ToolError("File changed since it was read; read it again")
                original = before.decode("utf-8")
                if not old or original.count(old) != 1:
                    raise ToolError("old must match exactly one non-empty occurrence")
                after = original.replace(old, new, 1).encode("utf-8")
            if len(after) > MAX_FILE:
                raise ToolError("Result exceeds the file-size limit")
            if before == after:
                raise ToolError("Change does not alter the file")
            diff = "".join(difflib.unified_diff(
                (before or b"").decode("utf-8").splitlines(keepends=True),
                after.decode("utf-8").splitlines(keepends=True),
                fromfile="a/" + name, tofile="b/" + name))
            previews.append(diff + "\nExact replacement (JSON-escaped):\n" + json.dumps(item, ensure_ascii=True))
            prepared.append((name, before, after))
        preview = "\n".join(previews)
        if len(preview.encode()) > 60000:
            raise ToolError("Diff too large for complete review; split the change")
        if not self._permission("APPLY", preview):
            return {"status": "denied", "changed": []}
        # Revalidate ALL targets after approval and before writing any file.
        for name, before, _ in prepared:
            target = self.path(name)
            current = self._read(name) if target.exists() else None
            if current != before:
                raise ToolError("Files changed during review; no changes were applied")
        batch = self.history / uuid.uuid4().hex
        batch.mkdir(parents=True, mode=0o700)
        manifest = {"workspace": str(self.root), "files": []}
        for index, (name, before, after) in enumerate(prepared):
            if before is not None:
                backup = batch / f"{index}.original"
                backup.write_bytes(before)
                backup.chmod(0o600)
            manifest["files"].append({"path": name, "backup": f"{index}.original" if before is not None else None,
                                      "before_sha256": digest(before) if before is not None else None,
                                      "after_sha256": digest(after)})
        (batch / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        changed = []
        try:
            for name, before, after in prepared:
                if self.cancel.is_set():
                    raise ToolError("Stopped before the next file write")
                target = self.path(name)
                current = self._read(name) if target.exists() else None
                if current != before:
                    raise ToolError("File changed immediately before write")
                mode = stat.S_IMODE(target.stat().st_mode) if before is not None else 0o600
                fd, temporary = tempfile.mkstemp(prefix=".helix-edit-", dir=target.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(after)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.chmod(temporary, mode)
                    self.path(name)  # check again; not an OS compare-and-swap guarantee
                    os.replace(temporary, target)
                    changed.append(name)
                    if self._read(name) != after:
                        raise ToolError("Read-back verification failed")
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
        except (OSError, ToolError) as exc:
            result = {"status": "partial_or_uncertain", "changed": changed,
                      "backup_directory": str(batch), "error": str(exc)}
            self.receipts.append({"tool": "edit", **result})
            # Do not clobber concurrent changes with an automatic rollback.
            return result
        result = {"status": "applied", "changed": changed, "backup_directory": str(batch)}
        self.receipts.append({"tool": "edit", **result})
        return result

    @staticmethod
    def _kill(process: subprocess.Popen) -> None:
        try:
            if os.name == "nt":
                system = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
                subprocess.run([str(system), "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            pass
        if process.poll() is None:
            process.kill()

    def run_command(self, argv: list[str], timeout=120) -> dict:
        integer(timeout, 1, 600)
        if not isinstance(argv, list) or not 1 <= len(argv) <= 64:
            raise ToolError("Command must be an argv array")
        argv = [text(arg, 6000, empty=False) for arg in argv]
        if sum(len(arg) for arg in argv) > 16000:
            raise ToolError("Command is too long")
        # Resolve the executable now, outside CWD. No implicit .cmd/.bat shell.
        program = sys.executable if argv[0] in {"python", "python3"} else shutil.which(argv[0])
        if not program:
            raise ToolError("Executable not found")
        executable = Path(program).resolve()
        if (executable.is_relative_to(self.root) and executable != Path(sys.executable).resolve()) or executable.suffix.casefold() in {".bat", ".cmd"}:
            raise ToolError("Direct workspace executables/batch wrappers are disabled; use an explicit interpreter and review it")
        argv[0] = str(executable)
        preview = ("UNSANDBOXED command: can change files OUTSIDE this repository, access the network, "
                   "read user-accessible secrets, or start applications. Do not run HELIX as Administrator.\n"
                   f"Working directory: {self.root}\nTimeout: {timeout}s\n"
                   + json.dumps(argv, ensure_ascii=True, indent=2))
        if not self._permission("RUN", preview):
            return {"status": "denied"}
        allowed_env = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "HOME",
                       "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PATHEXT", "LANG"}
        env = {k: v for k, v in os.environ.items() if k.upper() in allowed_env}
        env.update({"PYTHONIOENCODING": "utf-8", "GIT_TERMINAL_PROMPT": "0"})
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(argv, cwd=self.root, env=env, shell=False, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **options)
        captured = bytearray()
        overflow, done = threading.Event(), threading.Event()
        def collect():
            try:
                while chunk := process.stdout.read(4096):
                    remaining = MAX_OUTPUT - len(captured)
                    captured.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        overflow.set()
                        break
            finally:
                done.set()
        reader = threading.Thread(target=collect, daemon=True)
        reader.start()
        started, stopped = time.monotonic(), None
        try:
            while process.poll() is None or not done.is_set():
                if self.cancel.is_set():
                    stopped = "cancelled"
                elif overflow.is_set():
                    stopped = "output_limit"
                elif time.monotonic() - started > timeout:
                    stopped = "timeout"
                if stopped:
                    self._kill(process)
                    break
                time.sleep(0.03)
            process.wait(timeout=10)
        except BaseException:
            self._kill(process)
            raise
        finally:
            reader.join(timeout=2)
            if done.is_set():
                process.stdout.close()
        result = {"status": stopped or ("output_limit" if overflow.is_set() else "completed"),
                  "argv": argv, "exit_code": process.returncode,
                  "output": captured.decode("utf-8", errors="replace")}
        self.receipts.append({"tool": "run_command", **{k: v for k, v in result.items() if k != "output"}})
        return result
