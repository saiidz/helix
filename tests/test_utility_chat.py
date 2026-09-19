import asyncio
import json
import re
import threading
from types import SimpleNamespace

import pytest

from helix.core import ChatRequest, Message, Role
from helix.ledger import Ledger
from helix.memory import MemoryStore
from helix.utility_chat import (
    UtilityChat,
    clock_result,
    detect_clock_request,
    detect_profile_request,
)


KEY = "test-clock-only-key-123456789012345"


class Memory:
    def __init__(self):
        self.rows = []

    def save_message(self, *row):
        self.rows.append(row)


def request(text, *, role=None, conversation_id=None, web_mode="legacy"):
    return ChatRequest(
        messages=[Message(role="user", content=text)],
        role=role,
        conversation_id=conversation_id,
        web_mode=web_mode,
    )


@pytest.fixture
def service(tmp_path):
    return UtilityChat(
        api_key=KEY,
        ledger=Ledger(tmp_path / "ledger.sqlite3"),
        memory=Memory(),
        gate=threading.BoundedSemaphore(2),
        monthly_limit=10_000_000,
    )


async def frames(response):
    return [json.loads(frame) async for frame in response.body_iterator]


@pytest.mark.parametrize("text", [
    "what time is it now",
    "What time is it?",
    "current time",
    "time now",
])
def test_detects_local_time_questions(text):
    assert detect_clock_request(text) == "time"


@pytest.mark.parametrize("text", [
    "what date is it",
    "what day is it today?",
    "today's date",
    "current date",
])
def test_detects_local_date_questions(text):
    assert detect_clock_request(text) == "date"


@pytest.mark.parametrize("text", [
    "wha date is it today",
    "wat date is it today?",
    "wht day is it today",
    "wats the time",
    "time rn",
])
def test_clock_intent_tolerates_common_short_typos(text):
    expected = "time" if "time" in text.lower() else "date"
    assert detect_clock_request(text) == expected


@pytest.mark.parametrize("text,kind", [
    ("who am i?", "profile"),
    ("what do you know about me", "profile"),
    ("what do you remember about me?", "profile"),
    ("tell me about myself", "profile"),
    ("what is my name?", "name"),
    ("do you remember my name", "name"),
])
def test_detects_self_profile_questions(text, kind):
    assert detect_profile_request(text) == kind


def test_location_specific_time_falls_through():
    assert detect_clock_request("what time is it in Tokyo") is None
    assert detect_clock_request("what time is the game") is None


def test_clock_result_is_timezone_aware():
    result = clock_result("both")
    assert result["timestamp"]
    assert result["timezone"]
    assert "\n" in result["text"]
    assert re.search(r"\d{1,2}:\d{2} [AP]M", result["text"])


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("role", [None, Role.COMPANION, Role.ENGINEER, Role.SAGE])
def test_clock_reply_bypasses_model_and_web(service, stream, role):
    result = service.reply(
        request("what time is it now", role=role, web_mode="on"),
        "clock-request-0001",
        stream=stream,
    )
    if stream:
        events = asyncio.run(frames(result))
        assert [event["type"] for event in events] == ["meta", "delta", "done"]
        result = {**events[0], **events[-1], "text": events[1]["text"]}
    assert result["role"] == (role.value if role else "companion")
    assert result["provider_called"] is False
    assert result["model_id"] == "helix/host-clock"
    assert result["model_cost_usd"] == 0
    assert result["answer_verified"] is True
    assert result["verification_method"] == "host_clock"
    assert result["web_sources"] == []
    assert result["web_used"] is False
    assert re.search(r"\d{1,2}:\d{2} [AP]M", result["text"])


def test_non_clock_question_keeps_normal_chat_path(service):
    assert service.reply(request("explain why time complexity matters"), "clock-no-match") is None
    assert service.ledger.summary()["counts"] == {}


def test_clock_history_is_saved_without_model(service):
    result = service.reply(
        request("current time", conversation_id="conversation-123"),
        "clock-history-1",
    )
    assert result["answer_verified"]
    assert len(service.memory.rows) == 2


@pytest.fixture
def profile_service(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    return UtilityChat(
        api_key=KEY,
        ledger=Ledger(tmp_path / "ledger-profile.sqlite3"),
        memory=memory,
        gate=threading.BoundedSemaphore(2),
        monthly_limit=10_000_000,
    )


@pytest.mark.parametrize("stream", [False, True])
def test_identity_uses_explicit_local_profile_memory_without_model(profile_service, stream):
    profile_service.memory.add_memory(
        "My name is Mira",
        kind="profile",
        source="explicit_user",
        pinned=True,
        importance=1.0,
    )
    profile_service.memory.add_memory(
        "I prefer concise answers",
        kind="preference",
        source="explicit_user",
        importance=0.8,
    )
    profile_service.memory.add_memory(
        "The HELIX repo uses Python",
        kind="project",
        source="explicit_user",
        importance=1.0,
    )

    result = profile_service.reply(
        request("who am i?"),
        "profile-request-0001",
        stream=stream,
    )
    if stream:
        events = asyncio.run(frames(result))
        assert [event["type"] for event in events] == ["meta", "delta", "done"]
        result = {**events[0], **events[-1], "text": events[1]["text"]}

    assert result["provider_called"] is False
    assert result["provider_mode"] == "local_memory"
    assert result["model_id"] == "helix/profile-memory"
    assert result["model_cost_usd"] == 0
    assert result["answer_verified"] is False
    assert result["verification_method"] == "local_memory"
    assert "My name is Mira" in result["text"]
    assert "I prefer concise answers" in result["text"]
    assert "HELIX repo" not in result["text"]
    assert result["memory_used"]
    assert result["web_sources"] == []


def test_name_question_prefers_name_memory(profile_service):
    profile_service.memory.add_memory("My birthday is September 14", kind="profile")
    profile_service.memory.add_memory("My name is Mira", kind="profile")
    result = profile_service.reply(
        request("what's my name?"),
        "profile-name-request",
    )
    assert result["text"] == "You told me: My name is Mira"
    assert len(result["memory_used"]) == 1


@pytest.mark.parametrize("stream", [False, True])
def test_identity_respects_memory_off(profile_service):
    profile_service.memory.add_memory("My name is Mira", kind="profile", pinned=True)
    result = profile_service.reply(
        request("who am i?", web_mode="off").model_copy(update={"memory_enabled": False}),
        "profile-memory-off-request",
    )
    assert result["provider_called"] is False
    assert result["verification_method"] == "local_memory_disabled"
    assert result["tools_used"] == []
    assert result["memory_used"] == []
    assert "memory is off" in result["text"].lower()
    assert "My name is Mira" not in result["text"]


def test_identity_without_profile_memory_is_actionable_and_model_free(profile_service, stream):
    result = profile_service.reply(
        request("who am i?"),
        "profile-empty-request",
        stream=stream,
    )
    if stream:
        events = asyncio.run(frames(result))
        result = {**events[0], **events[-1], "text": events[1]["text"]}

    assert result["provider_called"] is False
    assert result["model_cost_usd"] == 0
    assert result["profile_memory_found"] is False
    assert result["verification_method"] == "local_memory"
    assert "don't have a profile memory saved" in result["text"].lower()
    assert "remember that my name is" in result["text"].lower()
