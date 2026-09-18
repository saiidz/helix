import pytest

from helix.files import FileStore


def test_file_store_add_retrieve_list_delete(tmp_path):
    store = FileStore(tmp_path / "files.sqlite3")
    item = store.add(
        "conversation-1234",
        "app.py",
        "def hello():\n    return 'world'\n",
        "text/x-python",
    )

    listed = store.list("conversation-1234")
    assert len(listed) == 1
    assert listed[0]["id"] == item["id"]
    assert listed[0]["name"] == "app.py"

    hits = store.retrieve("conversation-1234", "review this Python app.py file")
    assert hits
    assert hits[0]["id"] == item["id"]
    assert "def hello" in hits[0]["excerpt"]

    assert store.delete(item["id"], "conversation-1234") is True
    assert store.list("conversation-1234") == []


def test_file_store_rejects_non_text(tmp_path):
    store = FileStore(tmp_path / "files.sqlite3")

    with pytest.raises(ValueError):
        store.add(
            "conversation-1234",
            "photo.png",
            "not really an image",
            "image/png",
        )


def test_file_store_caps_context(tmp_path):
    store = FileStore(tmp_path / "files.sqlite3")
    for index in range(4):
        store.add(
            "conversation-1234",
            f"part-{index}.txt",
            ("needle " + ("x" * 5000)),
            "text/plain",
        )

    hits = store.retrieve("conversation-1234", "needle attached file", limit=4)
    assert len(hits) <= 4
    assert sum(len(item["excerpt"]) for item in hits) <= 12000
