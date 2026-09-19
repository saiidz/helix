from pathlib import Path

import pytest

from helix.engineer_jobs import EngineerJobStore


def test_job_history_persists_events_and_result(tmp_path):
    path = tmp_path / "engineer-jobs.sqlite3"
    store = EngineerJobStore(path)
    job = store.create("Fix checkout", str(tmp_path / "repo"))
    assert job["status"] == "queued"
    assert job["events"] == []

    store.set_status(job["id"], "running")
    store.append_event(job["id"], 1, "step", 1)
    store.append_event(job["id"], 2, "result", {"status": "completed", "exit_code": 0})
    store.finish(job["id"], "model_finished", {"status": "model_finished", "steps": 2}, 1)

    reopened = EngineerJobStore(path)
    loaded = reopened.get(job["id"])
    assert loaded["status"] == "model_finished"
    assert loaded["receipt_count"] == 1
    assert loaded["result"]["steps"] == 2
    assert [event["kind"] for event in loaded["events"]] == ["step", "result"]
    assert reopened.list()[0]["id"] == job["id"]
    assert "result" not in reopened.list()[0]


def test_inflight_jobs_become_interrupted_on_restart(tmp_path):
    path = tmp_path / "engineer-jobs.sqlite3"
    store = EngineerJobStore(path)
    jobs = []
    for status in ("queued", "running", "waiting_for_approval", "stopping"):
        job = store.create("Task " + status, str(tmp_path / "repo"))
        store.set_status(job["id"], status)
        jobs.append(job["id"])

    reopened = EngineerJobStore(path)
    assert {reopened.get(job_id)["status"] for job_id in jobs} == {"interrupted"}


def test_finished_jobs_are_not_rewritten_on_restart(tmp_path):
    path = tmp_path / "engineer-jobs.sqlite3"
    store = EngineerJobStore(path)
    job = store.create("Finished task", str(tmp_path / "repo"))
    store.finish(job["id"], "model_finished", {"status": "model_finished"}, 0)
    EngineerJobStore(path)
    assert EngineerJobStore(path).get(job["id"])["status"] == "model_finished"


def test_store_bounds_and_missing_job(tmp_path):
    store = EngineerJobStore(tmp_path / "jobs.sqlite3")
    with pytest.raises(ValueError):
        store.create("", "repo")
    with pytest.raises(ValueError):
        store.create("x" * 6001, "repo")
    with pytest.raises(LookupError):
        store.set_status("missing", "running")
    assert store.get("missing") is None
