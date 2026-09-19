"""Persistent Engineer-job API tests with deterministic model fixtures."""
import json
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from helix.engineer_api import install_agent_routes

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
        tmp_path / "engineer-jobs.sqlite3",
    )
    return app


def wait_done(client, timeout=4):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        payload = client.get(PREFIX + "/status", headers=AUTH).json()
        if payload["session"] and not payload["session"]["active"]:
            return payload
        time.sleep(.02)
    raise AssertionError("Engineer fixture did not finish")


def test_job_api_persists_after_app_restart(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("value = 1\n", encoding="utf-8")
    actions = [
        {"tool": "read_file", "path": "main.py"},
        {"tool": "finish", "summary": "Inspected the file; no changes requested."},
    ]
    app = app_for(tmp_path, root, actions)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        start = client.post(PREFIX + "/start", headers=AUTH, json={"task": "Inspect main.py"})
        assert start.status_code == 200, start.text
        job_id = start.json()["job_id"]
        done = wait_done(client)
        assert done["session"]["job_id"] == job_id
        detail = client.get(PREFIX + "/jobs/" + job_id, headers=AUTH).json()["job"]
        assert detail["status"] == "model_finished"
        assert detail["task"] == "Inspect main.py"
        assert any(event["kind"] == "session_result" for event in detail["events"])
        assert client.get(PREFIX + "/jobs", headers=AUTH).json()["jobs"][0]["id"] == job_id

    restarted = app_for(tmp_path, root, [{"tool": "finish", "summary": "unused"}])
    with TestClient(restarted, base_url="http://127.0.0.1") as client:
        detail = client.get(PREFIX + "/jobs/" + job_id, headers=AUTH)
        assert detail.status_code == 200
        assert detail.json()["job"]["status"] == "model_finished"


def test_job_history_routes_require_auth(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    app = app_for(tmp_path, root, [{"tool": "finish", "summary": "unused"}])
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get(PREFIX + "/jobs").status_code == 401
        assert client.get(PREFIX + "/jobs/anything").status_code == 401


def test_status_is_truthful_about_persistence_and_resume(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    app = app_for(tmp_path, root, [{"tool": "finish", "summary": "unused"}])
    with TestClient(app, base_url="http://127.0.0.1") as client:
        status = client.get(PREFIX + "/status", headers=AUTH).json()
        assert status["history_persistent"] is True
        assert status["resume_after_restart"] is False
        assert status["os_sandbox"] is False
