from pathlib import Path

from fastapi.testclient import TestClient

from helix.core import Settings
from helix.providers import Completion
from helix.server import create_app


KEY = "test-only-key-not-a-secret-12345678"
BASE = Path(__file__).resolve().parents[1]
AUTH = {"Authorization": f"Bearer {KEY}"}


def client(tmp_path):
    settings = Settings.from_file(BASE / "config/demo.json")
    return TestClient(create_app(settings, KEY, tmp_path / "ledger.sqlite3", ["testserver"]))


def test_memory_api_and_chat_injection(tmp_path, monkeypatch):
    captured = {}

    def fake_complete(profile, messages, max_output):
        captured["messages"] = messages
        return Completion("I remember that preference.", 10, 5)

    monkeypatch.setattr("helix.server.complete", fake_complete)
    c = client(tmp_path)

    created = c.post(
        "/api/memories",
        headers=AUTH,
        json={
            "content": "I prefer concise answers",
            "kind": "preference",
            "pinned": True,
            "importance": 0.9,
        },
    )
    assert created.status_code == 200, created.text

    response = c.post(
        "/api/chat",
        headers={**AUTH, "Idempotency-Key": "memory-chat-request-0001"},
        json={
            "messages": [{"role": "user", "content": "Please answer concisely"}],
            "memory_enabled": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["memory_used"]

    system_messages = [
        message["content"]
        for message in captured["messages"]
        if message["role"] == "system"
    ]
    assert any("I prefer concise answers" in text for text in system_messages)


def test_explicit_remember_and_conversation_persistence(tmp_path, monkeypatch):
    def fake_complete(profile, messages, max_output):
        return Completion("I will remember that.", 10, 5)

    monkeypatch.setattr("helix.server.complete", fake_complete)
    c = client(tmp_path)

    conversation = c.post(
        "/api/conversations",
        headers=AUTH,
        json={"title": "Memory test"},
    ).json()["conversation"]

    response = c.post(
        "/api/chat",
        headers={**AUTH, "Idempotency-Key": "memory-chat-request-0002"},
        json={
            "conversation_id": conversation["id"],
            "memory_enabled": True,
            "messages": [
                {
                    "role": "user",
                    "content": "Remember that my birthday is September 14",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["memory_saved"]["kind"] == "profile"

    stored = c.get(
        f"/api/conversations/{conversation['id']}",
        headers=AUTH,
    )
    assert stored.status_code == 200
    messages = stored.json()["conversation"]["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]

    memories = c.get("/api/memories", headers=AUTH).json()["memories"]
    assert len(memories) == 1
    assert "birthday" in memories[0]["content"].lower()
