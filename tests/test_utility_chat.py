import asyncio
import json
import re
import threading
from types import SimpleNamespace

import pytest

from helix.core import ChatRequest, Message, Role
from helix.ledger import Ledger
from helix.utility_chat import UtilityChat, clock_result, detect_clock_request


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
