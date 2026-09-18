"""Real HTTP router/approval tests with a deterministic local-model substitute."""
import json
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from helix.engineer_api import install_agent_routes

KEY = "test-only-local-access-key-0123456789"
AUTH = {"Authorization": "Bearer " + KEY}
PREFIX = "/api/engineer-agent"


@pytest.fixture
def connected(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("value = 1\n")
    import hashlib
    sha = hashlib.sha256(b"value = 1\n").hexdigest()
    actions = [
        {"tool": "read_file", "path": "main.py"},
        {"tool": "edit", "changes": [{"path": "main.py", "sha256": sha, "old": "1", "new": "2"}]},
        {"tool": "finish", "summary": "Fixture finished; actual tool receipts establish the edit."},
    ]
    def factory():
        iterator = iter(actions)
        return lambda _: json.dumps(next(iterator)), 24000
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=Path(__file__).parents[1] / "helix" / "static"))
    state = install_agent_routes(app, KEY, root, Path("unused.json"), factory, tmp_path / "history")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, root, state


def wait_for(client, condition, timeout=4):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        snapshot = client.get(PREFIX + "/status", headers=AUTH).json()
        if condition(snapshot):
            return snapshot
        time.sleep(.02)
    pytest.fail("Timed out waiting for fixture session")


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/status", None), ("POST", "/start", {"task": "Inspect"}),
    ("POST", "/stop", {}), ("POST", "/decision", {"approval_id": "a" * 24, "decision": "approve"})])
def test_all_control_endpoints_require_key(connected, method, path, body):
    client, _, _ = connected
    response = client.request(method, PREFIX + path, **({"json": body} if body is not None else {}))
    assert response.status_code == 401


def test_cross_origin_and_host_rejected(connected):
    client, _, _ = connected
    assert client.get(PREFIX + "/status", headers={**AUTH, "Origin": "https://attacker.invalid"}).status_code == 403
    assert client.get(PREFIX + "/status", headers={**AUTH, "Host": "attacker.invalid"}).status_code == 403


def test_actions_cannot_enable_arbitrary_workspace_or_approve_themselves(connected):
    client, _, _ = connected
    assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect", "workspace": "C:/"}).status_code == 422
    assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect", "approved": True}).status_code == 422
    assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect", "max_steps": True}).status_code == 422


def test_http_approval_gates_real_disk_edit_and_is_single_use(connected):
    client, root, _ = connected
    assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Change value to 2"}).status_code == 200
    pending = wait_for(client, lambda s: s["session"] and s["session"]["approval"])
    assert (root / "main.py").read_text() == "value = 1\n"
    assert pending["session"]["approval"]["kind"] == "APPLY"
    assert "Exact replacement" in pending["session"]["approval"]["preview"]
    assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "another"}).status_code == 409
    payload = {"approval_id": pending["session"]["approval"]["id"], "decision": "approve"}
    assert client.post(PREFIX + "/decision", headers=AUTH, json=payload).status_code == 200
    done = wait_for(client, lambda s: not s["session"]["active"])
    assert done["session"]["status"] == "model_finished"
    assert (root / "main.py").read_text() == "value = 2\n"
    assert client.post(PREFIX + "/decision", headers=AUTH, json=payload).status_code == 409
    assert done["session"]["receipts"][0]["status"] == "applied"


def test_deny_and_stop_never_write(connected):
    client, root, _ = connected
    client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect"})
    pending = wait_for(client, lambda s: s["session"] and s["session"]["approval"])
    payload = {"approval_id": pending["session"]["approval"]["id"], "decision": "approve"}
    assert client.post(PREFIX + "/stop", headers=AUTH, json={}).status_code == 200
    wait_for(client, lambda s: not s["session"]["active"])
    assert (root / "main.py").read_text() == "value = 1\n"
    assert client.post(PREFIX + "/decision", headers=AUTH, json=payload).status_code == 409


def test_default_agent_is_disabled_and_does_not_start_model(tmp_path):
    app = FastAPI()
    def forbidden():
        pytest.fail("Disabled agent created a provider")
    install_agent_routes(app, KEY, None, Path("unused.json"), forbidden, tmp_path / "history")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get(PREFIX + "/status", headers=AUTH)
        assert response.json()["enabled"] is False
        assert response.json()["os_sandbox"] is False
        assert client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect"}).status_code == 409


def test_agent_page_and_external_assets_served(connected):
    client, _, _ = connected
    page = client.get("/agent")
    assert page.status_code == 200
    assert '/static/agent.js' in page.text and '/static/agent.css' in page.text
    assert 'onclick=' not in page.text
    for asset in ("agent.js", "agent.css"):
        assert client.get("/static/" + asset).status_code == 200


def test_wrong_approval_id_cannot_mutate(connected):
    client, root, _ = connected
    client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect"})
    wait_for(client, lambda s: s["session"] and s["session"]["approval"])
    assert client.post(PREFIX + "/decision", headers=AUTH, json={"approval_id": "x" * 24, "decision": "approve"}).status_code == 409
    assert (root / "main.py").read_text() == "value = 1\n"


def test_event_cursor_is_scoped_to_session(connected):
    client, _, _ = connected
    client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect"})
    pending = wait_for(client, lambda s: s["session"] and s["session"]["approval"])
    session = pending["session"]
    same = client.get(PREFIX + f'/status?since={session["cursor"]}&session_id={session["id"]}', headers=AUTH).json()
    assert same["session"]["events"] == []
    other = client.get(PREFIX + '/status?since=999999&session_id=old-session', headers=AUTH).json()
    assert other["session"]["events"]
