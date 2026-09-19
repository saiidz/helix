import hashlib
import io
import threading

import pytest

from helix.engineer_tools import ToolError, Workspace
from helix.safety import SafetyError, SafetyStore


class TTY(io.StringIO):
    def isatty(self):
        return True


class NonTTY(io.StringIO):
    def isatty(self):
        return False


def make_workspace(tmp_path, safety, approve=lambda *_: True):
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    return Workspace(
        root,
        tmp_path / "history",
        approve,
        safety_check=safety.is_locked,
    )


def test_lock_persists_and_reset_requires_interactive_terminal(tmp_path):
    path = tmp_path / "safety.sqlite3"
    safety = SafetyStore(path)
    assert safety.status()["locked"] is False
    locked = safety.lock("fixture")
    assert locked["locked"] is True
    assert locked["generation"] == 1
    assert SafetyStore(path).is_locked() is True

    with pytest.raises(SafetyError, match="interactive"):
        SafetyStore(path).unlock_interactive(stream=NonTTY())
    assert SafetyStore(path).is_locked() is True

    reset = SafetyStore(path).unlock_interactive(
        stream=TTY(),
        input_fn=lambda _: "RESET HELIX LOCKDOWN 1",
    )
    assert reset["locked"] is False
    assert reset["generation"] == 1


def test_wrong_reset_phrase_keeps_lock(tmp_path):
    safety = SafetyStore(tmp_path / "safety.sqlite3")
    safety.lock("fixture")
    with pytest.raises(SafetyError, match="did not match"):
        safety.unlock_interactive(stream=TTY(), input_fn=lambda _: "no")
    assert safety.is_locked()


def test_workspace_fails_closed_for_reads_edits_and_commands(tmp_path):
    safety = SafetyStore(tmp_path / "safety.sqlite3")
    ws = make_workspace(tmp_path, safety)
    (ws.root / "main.py").write_bytes(b"value = 1\n")
    sha = hashlib.sha256(b"value = 1\n").hexdigest()
    safety.lock("fixture")

    with pytest.raises(ToolError, match="Emergency Lockdown"):
        ws.read_file("main.py")
    with pytest.raises(ToolError, match="Emergency Lockdown"):
        ws.edit([{"path": "main.py", "sha256": sha, "old": "1", "new": "2"}])
    with pytest.raises(ToolError, match="Emergency Lockdown"):
        ws.run_command(["python", "-c", "print('no')"])
    assert (ws.root / "main.py").read_text() == "value = 1\n"


def test_lock_during_approval_invalidates_approval(tmp_path):
    safety = SafetyStore(tmp_path / "safety.sqlite3")

    def approve(*_):
        safety.lock("during approval")
        return True

    ws = make_workspace(tmp_path, safety, approve)
    (ws.root / "main.py").write_bytes(b"value = 1\n")
    sha = hashlib.sha256(b"value = 1\n").hexdigest()
    result = ws.edit([{"path": "main.py", "sha256": sha, "old": "1", "new": "2"}])
    assert result == {"status": "denied", "changed": []}
    assert (ws.root / "main.py").read_text() == "value = 1\n"


def test_lock_terminates_running_command(tmp_path):
    safety = SafetyStore(tmp_path / "safety.sqlite3")
    ws = make_workspace(tmp_path, safety)
    timer = threading.Timer(.2, lambda: safety.lock("running command"))
    timer.start()
    try:
        result = ws.run_command(
            ["python", "-c", "import time; time.sleep(10)"],
            timeout=5,
        )
    finally:
        timer.join()
    assert result["status"] == "lockdown"
    assert safety.is_locked()


def test_safety_callback_errors_fail_closed(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("x=1\n", encoding="utf-8")

    def broken():
        raise RuntimeError("unavailable")

    ws = Workspace(root, tmp_path / "history", lambda *_: True, safety_check=broken)
    with pytest.raises(ToolError, match="Emergency Lockdown"):
        ws.read_file("main.py")
