"""Emergency Lockdown API behavior with deterministic local fixtures."""
import hashlib
import json
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from helix.engineer_api import install_agent_routes
from helix.safety import SafetyStore

KEY = "test-only-local-access-key-0123456789"
AUTH = {"Authorization": "Bearer " + KEY}
PREFIX = "/api/engineer-agent"


def app_for(tmp_path, root, actions):
    def factory():
        iterator = iter(actions)
        return lambda _: json.dumps(next(iterator)), 24000

    app = FastAPI()
    install_agent_routes(
        app,
        KEY,
        root,
        Path("unused.json"),
        factory,
        tmp_path / "history",
        tmp_path / "jobs.sqlite3",
        tmp_path / "safety.sqlite3",
    )
    return app


def wait_for(client, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get(PREFIX + "/status", headers=AUTH).json()
        if predicate(status):
            return status
        time.sleep(.02)
    raise AssertionError("Timed out waiting for lockdown fixture")


def test_lockdown_persists_blocks_start_and_has_no_http_reset(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    app = app_for(tmp_path, root, [{"tool": "finish", "summary": "unused"}])
    with TestClient(app, base_url="http://127.0.0.1") as client:
        status = client.get(PREFIX + "/status", headers=AUTH).json()
        assert status["actions_enabled"] is True
        assert status["lockdown"]["locked"] is False

        locked = client.post(PREFIX + "/lockdown", headers=AUTH, json={})
        assert locked.status_code == 200
        assert locked.json()["lockdown"]["locked"] is True
        status = client.get(PREFIX + "/status", headers=AUTH).json()
        assert status["enabled"] is True
        assert status["actions_enabled"] is False
        assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect"}).status_code == 423
        assert client.post(PREFIX + "/unlock", headers=AUTH, json={}).status_code == 404

    restarted = app_for(tmp_path, root, [{"tool": "finish", "summary": "unused"}])
    with TestClient(restarted, base_url="http://127.0.0.1") as client:
        assert client.get(PREFIX + "/status", headers=AUTH).json()["lockdown"]["locked"] is True
        assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect"}).status_code == 423


def test_lockdown_invalidates_pending_edit_approval(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_bytes(b"value = 1\n")
    sha = hashlib.sha256(b"value = 1\n").hexdigest()
    actions = [
        {"tool": "read_file", "path": "main.py"},
        {"tool": "edit", "changes": [{"path": "main.py", "sha256": sha, "old": "1", "new": "2"}]},
        {"tool": "finish", "summary": "should not reach a write"},
    ]
    app = app_for(tmp_path, root, actions)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Change value"}).status_code == 200
        pending = wait_for(client, lambda s: s["session"] and s["session"]["approval"])
        approval = pending["session"]["approval"]
        assert approval["kind"] == "APPLY"

        assert client.post(PREFIX + "/lockdown", headers=AUTH, json={}).status_code == 200
        final = wait_for(client, lambda s: s["session"] and not s["session"]["active"])
        assert final["lockdown"]["locked"] is True
        assert final["session"]["status"] == "lockdown"
        assert (root / "main.py").read_text() == "value = 1\n"
        assert client.post(
            PREFIX + "/decision",
            headers=AUTH,
            json={"approval_id": approval["id"], "decision": "approve"},
        ).status_code == 423


def test_external_lock_is_observed_by_running_session(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    actions = [
        {
            "tool": "run_command",
            "argv": ["python", "-c", "import time; time.sleep(10)"],
            "timeout": 20,
        }
    ]
    app = app_for(tmp_path, root, actions)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Run fixture"}).status_code == 200
        pending = wait_for(client, lambda s: s["session"] and s["session"]["approval"])
        approval = pending["session"]["approval"]
        assert client.post(
            PREFIX + "/decision",
            headers=AUTH,
            json={"approval_id": approval["id"], "decision": "approve"},
        ).status_code == 200
        SafetyStore(tmp_path / "safety.sqlite3").lock("external fixture")
        final = wait_for(client, lambda s: s["session"] and not s["session"]["active"], timeout=6)
        assert final["lockdown"]["locked"] is True
        assert final["session"]["status"] == "lockdown"
