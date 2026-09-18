"""Offline tests: real file/process tools plus deterministic model fixtures."""
import hashlib
import json
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from helix.engineer_agent import dispatch, fit_context, parse_action, project_advice, run_agent
from helix.engineer_tools import MAX_FILE, MAX_OUTPUT, ToolError, Workspace, visible


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    return Workspace(root, tmp_path / "history", lambda *_: True)


def put(ws, path="main.py", data=b"answer = 1\n"):
    target = ws.root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def change(sha, path="main.py", old="1", new="2"):
    return {"path": path, "sha256": sha, "old": old, "new": new}


@pytest.mark.parametrize("path", ["../x", "/tmp/x", "C:/temp/x", "a//b", "a/./b", "a/../b", "x:stream",
                                  "x.", "x ", "CON", "a/NUL.txt", "a/COM1", "a/\x1bb", "a\x00b",
                                  ".git/config", ".env", ".env.local", ".ssh/id_rsa", "config/local.json",
                                  "secret.pem", "node_modules/pkg/index.js", "data.sqlite3", ".npmrc"])
def test_unsafe_paths(ws, path):
    with pytest.raises(ToolError):
        ws.path(path)


def test_workspace_boundary(tmp_path):
    with pytest.raises(ToolError):
        Workspace(Path.home(), tmp_path / "history", lambda *_: True)
    with pytest.raises(ToolError):
        Workspace(tmp_path, tmp_path / "history", lambda *_: True)


def test_symlink_and_hardlink(ws, tmp_path):
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    try:
        (ws.root / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("Symlink permission not available on this host")
    with pytest.raises(ToolError):
        ws.read_file("link.txt")
    os.link(outside, ws.root / "hard.txt")
    with pytest.raises(ToolError):
        ws.read_file("hard.txt")


def test_symlink_directory(ws, tmp_path):
    try:
        (ws.root / "escape").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink permission not available on this host")
    with pytest.raises(ToolError):
        ws.path("escape/private.txt")
    assert ws.list_files()["files"] == []


def test_read_chunks_and_crlf(ws):
    data = ("α\r\n" * 3000).encode()
    sha = put(ws, data=data)
    result = ws.read_file("main.py", 6000, 30)
    assert result["sha256"] == sha
    assert result["text"] == data.decode()[6000:6030]
    assert result["next_offset"] == 6030
    assert result["characters"] == 9000


@pytest.mark.parametrize("data", [b"x\x00y", b"\xff", b"x" * (MAX_FILE + 1)])
def test_binary_encoding_and_size_limits(ws, data):
    put(ws, data=data)
    with pytest.raises(ToolError):
        ws.read_file("main.py")


def test_list_exclusions_and_limits(ws):
    put(ws, "main.py")
    put(ws, ".env", b"secret")
    put(ws, "node_modules/a.js")
    put(ws, ".agents/skills/review/SKILL.md", b"Review carefully")
    listing = ws.list_files()
    assert sorted(listing["files"]) == [".agents/skills/review/SKILL.md", "main.py"]
    assert ws.list_files(1)["truncated"]


def test_search_literal_and_limit(ws):
    put(ws, data=(b"[abc] one\n" * 40))
    result = ws.search("[abc]")
    assert len(result["matches"]) == 30 and result["truncated"]
    assert ws.search("a.*b")["matches"] == []


def test_edit_real_file_backup_hash_and_crlf(ws):
    sha = put(ws, data=b"answer = 1\r\n")
    result = ws.edit([change(sha)])
    assert result["status"] == "applied"
    assert (ws.root / "main.py").read_bytes() == b"answer = 2\r\n"
    backup = Path(result["backup_directory"])
    assert (backup / "0.original").read_bytes() == b"answer = 1\r\n"
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["files"][0]["before_sha256"] == sha
    assert manifest["files"][0]["after_sha256"] == hashlib.sha256(b"answer = 2\r\n").hexdigest()


def test_new_file_and_missing_parent(ws):
    assert ws.edit([change(None, "new.py", "", "x=1\n")])["status"] == "applied"
    with pytest.raises(ToolError):
        ws.edit([change(None, "missing/x.py", "", "x=1\n")])


def test_stale_hash_does_not_write(ws):
    sha = put(ws)
    put(ws, data=b"answer = 3\n")
    with pytest.raises(ToolError):
        ws.edit([change(sha)])
    assert (ws.root / "main.py").read_bytes() == b"answer = 3\n"
    assert not ws.history.exists()


def test_change_during_approval_refused(ws):
    sha = put(ws)
    def approve(*_):
        put(ws, data=b"concurrent change\n")
        return True
    ws.approve = approve
    with pytest.raises(ToolError):
        ws.edit([change(sha)])
    assert (ws.root / "main.py").read_bytes() == b"concurrent change\n"


def test_denial_remembered_and_no_write(ws):
    sha = put(ws)
    calls = []
    ws.approve = lambda *args: calls.append(args) or False
    for _ in range(2):
        assert ws.edit([change(sha)])["status"] == "denied"
    assert len(calls) == 1 and not ws.history.exists()


def test_nonboolean_approval_does_not_write(ws):
    sha = put(ws)
    ws.approve = lambda *_: "true"
    assert ws.edit([change(sha)])["status"] == "denied"


def test_multiple_files_and_duplicate_targets(ws):
    a, b = put(ws), put(ws, "other.py")
    with pytest.raises(ToolError):
        ws.edit([change(a), change(a, "MAIN.py")])
    result = ws.edit([change(a), change(b, "other.py")])
    assert result["changed"] == ["main.py", "other.py"]


def test_partial_failure_has_recovery_and_no_false_success(ws, monkeypatch):
    a, b = put(ws), put(ws, "other.py")
    replace = os.replace
    def fail_second(source, dest):
        if Path(dest).name == "other.py":
            raise OSError("disk failure fixture")
        return replace(source, dest)
    monkeypatch.setattr(os, "replace", fail_second)
    result = ws.edit([change(a), change(b, "other.py")])
    assert result["status"] == "partial_or_uncertain"
    assert result["changed"] == ["main.py"]
    assert (Path(result["backup_directory"]) / "1.original").read_bytes() == b"answer = 1\n"
    assert not list(ws.root.glob(".helix-edit-*"))


@pytest.mark.parametrize("old", ["", "missing", "a"])
def test_nonunique_or_empty_replacements(ws, old):
    sha = put(ws, data=b"a a\n")
    with pytest.raises(ToolError):
        ws.edit([change(sha, old=old)])


def test_terminal_escape_rendering():
    result = visible("\x1b[2J\r\bhidden\u202ehide\n")
    assert "\x1b" not in result and "\r" not in result and "\u202e" not in result
    assert "\\u001b" in result


def test_command_denied_no_process(ws, monkeypatch):
    ws.approve = lambda *_: False
    def bad(*_, **__):
        pytest.fail("A denied command was started")
    monkeypatch.setattr("subprocess.Popen", bad)
    assert ws.run_command([sys.executable, "-c", "print('no')"])["status"] == "denied"


def test_command_real_exit_code_output_environment_and_no_shell(ws, monkeypatch):
    monkeypatch.setenv("MY_API_TOKEN", "private-value")
    result = ws.run_command(["python", "-c",
        "import os,sys; print(os.getcwd()); print(os.environ.get('MY_API_TOKEN','ABSENT')); print(sys.argv[1]);sys.exit(3)",
        "$(echo no); & |"])
    assert result["status"] == "completed" and result["exit_code"] == 3
    assert str(ws.root) in result["output"]
    assert "ABSENT" in result["output"] and "private-value" not in result["output"]
    assert "$(echo no); & |" in result["output"]


def test_command_timeout_and_output_limit(ws):
    result = ws.run_command(["python", "-c", "import time; time.sleep(10)"], timeout=1)
    assert result["status"] == "timeout" and result["exit_code"] != 0
    result = ws.run_command(["python", "-c", "print('x'*1000000)"], timeout=5)
    assert result["status"] == "output_limit"
    assert len(result["output"].encode()) <= MAX_OUTPUT


def test_command_stop(ws):
    timer = threading.Timer(.2, ws.cancel.set)
    timer.start()
    result = ws.run_command(["python", "-c", "import time; time.sleep(10)"], timeout=5)
    timer.join()
    assert result["status"] == "cancelled"


def test_implicit_batch_wrapper_denied(ws, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: str(ws.root.parent / "npm.cmd"))
    with pytest.raises(ToolError):
        ws.run_command(["npm", "test"])


@pytest.mark.parametrize("raw", ["no", "[]", '{"tool":"search","tool":"edit"}',
                                 '{"tool":"read_file","offset":NaN}', '```json\n{}\n```'])
def test_malformed_json(raw):
    with pytest.raises(ToolError):
        parse_action(raw)


def test_unknown_tools_and_model_approval_cannot_bypass(ws):
    with pytest.raises(ToolError):
        dispatch(ws, {"tool": "approve", "value": True})
    with pytest.raises(ToolError):
        dispatch(ws, {"tool": "run_command", "argv": ["python"], "approved": True})
    with pytest.raises(ToolError):
        dispatch(ws, {"tool": "read_file", "path": "main.py", "limit": True})


def test_context_keeps_user_task():
    messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": "task"},
                {"role": "assistant", "content": "x" * 1000}, {"role": "user", "content": "old result"},
                {"role": "assistant", "content": "new"}, {"role": "user", "content": "new result"}]
    fitted = fit_context(messages, 400)
    assert fitted[1]["content"] == "task" and len(fitted) == 4


def test_skill_is_explicit_project_data(ws):
    put(ws, "AGENTS.md", b"Run tests")
    put(ws, ".agents/skills/review/SKILL.md", b"---\nname: review\n---\nReview code carefully")
    assert "Review code carefully" not in project_advice(ws, [])
    assert "Review code carefully" in project_advice(ws, ["review"])
    with pytest.raises(ToolError):
        project_advice(ws, ["../../outside"])


def test_repair_loop_real_failure_patch_pass_with_fixture_model(ws):
    put(ws, "calc.py", b"def add(a, b):\n    return a - b\n")
    put(ws, "test_calc.py", b"import unittest\nfrom calc import add\nclass Check(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n")
    sha = ws.read_file("calc.py")["sha256"]
    actions = iter([
        {"tool": "read_file", "path": "calc.py"},
        {"tool": "run_command", "argv": ["python", "-m", "unittest", "-q"]},
        {"tool": "edit", "changes": [change(sha, "calc.py", "a - b", "a + b")]},
        # Avoid bytecode timestamp/size reuse after the rapid equal-length fixture edit.
        {"tool": "run_command", "argv": ["python", "-B", "-c", "import calc; assert calc.add(2,3)==5"]},
        {"tool": "finish", "summary": "The addition fix was applied and the assertion passed."},
    ])
    # Disable pyc creation for the first run as well.
    first = list(actions)
    first[1]["argv"].insert(1, "-B")
    first[3] = {"tool":"run_command", "argv":["python","-B","-m","unittest","-q"]}
    iterator = iter(first)
    events = []
    result = run_agent(ws, "Fix addition and verify", lambda _: json.dumps(next(iterator)),
                       lambda kind, data: events.append((kind, data)))
    assert result["status"] == "model_finished"
    commands = [r for r in ws.receipts if r["tool"] == "run_command"]
    assert [r["exit_code"] for r in commands] == [1, 0]
    assert (ws.root / "calc.py").read_text().endswith("return a + b\n")
    assert len([r for r in ws.receipts if r["tool"] == "edit"]) == 1


def test_malformed_model_stops_after_three_errors(ws):
    result = run_agent(ws, "Inspect", lambda _: "bad json", lambda *_: None)
    assert result["status"] == "blocked_after_three_errors"
    assert not ws.receipts


def test_agent_step_and_cancel_limits(ws):
    result = run_agent(ws, "Inspect", lambda _: '{"tool":"list_files"}', lambda *_: None, max_steps=2)
    assert result["status"] == "step_limit"
    ws.cancel.set()
    result = run_agent(ws, "Inspect", lambda _: pytest.fail("Called after cancel"), lambda *_: None)
    assert result["status"] == "cancelled"


@pytest.mark.parametrize("kind,price", [("demo", 0), ("cloud", 0), ("local", 1)])
def test_local_provider_policy_rejects_demo_cloud_or_price(monkeypatch, kind, price):
    from helix.engineer_agent import local_completion
    profile = SimpleNamespace(kind=kind, input_usd_per_million=price, output_usd_per_million=0)
    settings = SimpleNamespace(profile=lambda _: profile)
    monkeypatch.setitem(sys.modules, "helix.core", SimpleNamespace(
        Role=SimpleNamespace(ENGINEER="engineer"), Settings=SimpleNamespace(from_file=lambda _: settings)))
    monkeypatch.setitem(sys.modules, "helix.providers", SimpleNamespace(complete=lambda *_: pytest.fail("Provider called")))
    with pytest.raises(ToolError):
        local_completion(Path("unused-fixture.json"))


def test_small_context_preserves_hash_and_explicit_file_continuation(ws):
    put(ws, data=b"line\n" * 2000)
    actions = iter([{"tool":"read_file", "path":"main.py", "limit":12000},
                    {"tool":"finish", "summary":"Read a bounded excerpt."}])
    messages_seen = []
    def model(messages):
        messages_seen.append(list(messages))
        return json.dumps(next(actions))
    result = run_agent(ws, "Inspect", model, lambda *_: None, context_budget=6000)
    assert result["status"] == "model_finished"
    observation = json.loads(messages_seen[1][-1]["content"].split("\n",1)[1])
    assert observation["sha256"] == ws.read_file("main.py")["sha256"]
    assert observation["truncated"] and observation["next_offset"] < 10000
