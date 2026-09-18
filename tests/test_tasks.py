from helix.tasks import TaskStore


def test_task_add_list_complete_reopen_delete(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    task = store.add("Review Helix PR", details="Run tests first", due_at="2026-09-19T15:00:00Z")

    open_tasks = store.list("open")
    assert len(open_tasks) == 1
    assert open_tasks[0]["title"] == "Review Helix PR"

    done = store.set_done(task["id"], True)
    assert done is not None
    assert done["status"] == "done"
    assert done["completed_at"] is not None
    assert store.list("open") == []

    reopened = store.set_done(task["id"], False)
    assert reopened["status"] == "open"
    assert reopened["completed_at"] is None

    assert store.delete(task["id"]) is True
    assert store.list("all") == []


def test_explicit_task_capture_is_deduped(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")

    first = store.capture_explicit("Add task buy cat food")
    second = store.capture_explicit("add task buy cat food")

    assert first is not None
    assert second is not None
    assert first["id"] == second["id"]
    assert len(store.list("open")) == 1


def test_non_task_chat_is_not_captured(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    assert store.capture_explicit("How does Helix work?") is None
    assert store.list("all") == []
