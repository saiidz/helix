from helix.memory import MemoryStore


def test_memory_add_list_retrieve_and_delete(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    item = store.add_memory(
        "I prefer concise answers",
        kind="preference",
        pinned=True,
        importance=0.9,
    )

    items = store.list_memories()
    assert len(items) == 1
    assert items[0]["id"] == item["id"]
    assert items[0]["pinned"] is True

    hits = store.retrieve("Please answer this concisely")
    assert hits and hits[0]["id"] == item["id"]

    assert store.delete_memory(item["id"]) is True
    assert store.list_memories() == []


def test_explicit_memory_capture_is_conservative(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    assert store.capture_explicit("I like coffee") is None

    saved = store.capture_explicit("Remember that my birthday is September 14")
    assert saved is not None
    assert saved["kind"] == "profile"
    assert "birthday" in saved["content"].lower()

    duplicate = store.capture_explicit("Remember that my birthday is September 14")
    assert duplicate["id"] == saved["id"]
    assert len(store.list_memories()) == 1


def test_conversation_persists_messages(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    conversation = store.create_conversation()

    store.save_message(conversation["id"], "user", "Hello Helix")
    store.save_message(conversation["id"], "assistant", "Hello!")

    loaded = store.get_conversation(conversation["id"])
    assert loaded is not None
    assert loaded["title"] == "Hello Helix"
    assert [m["role"] for m in loaded["messages"]] == ["user", "assistant"]
    assert [m["content"] for m in loaded["messages"]] == ["Hello Helix", "Hello!"]

    assert store.delete_conversation(conversation["id"]) is True
    assert store.get_conversation(conversation["id"]) is None
