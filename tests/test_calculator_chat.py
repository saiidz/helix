"""Service integration with the real ledger and fixture history/project stores."""
import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from helix.calculator_chat import CalculatorChat
from helix.ledger import Ledger

KEY = "test-calculator-only-key-1234567890"
EXPR = "9879878978979879879879-8546545645646546546*545646465464654/4564631641654*465464654/48949648"


class Request(SimpleNamespace):
    def model_dump_json(self):
        return json.dumps(vars(self), default=lambda x: vars(x), sort_keys=True)


def request(text="1+1", **kwargs):
    fields = dict(messages=[SimpleNamespace(content=text)], role=None, project_id=None,
                  conversation_id=None, max_output_tokens=512, web_enabled=False)
    fields.update(kwargs)
    return Request(**fields)


class Memory:
    def __init__(self):
        self.rows = []

    def get_conversation(self, identifier):
        return {"id": identifier} if identifier == "conversation-present" else None

    def save_message(self, *row):
        self.rows.append(row)


@pytest.fixture
def service(tmp_path):
    return CalculatorChat(api_key=KEY, ledger=Ledger(tmp_path / "ledger.db"), memory=Memory(),
                          projects=SimpleNamespace(get=lambda _: None), gate=threading.BoundedSemaphore(2),
                          monthly_limit=10_000_000)


async def frames(response):
    return [json.loads(frame) async for frame in response.body_iterator]


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("web", [False, True])
@pytest.mark.parametrize("role", [None, "companion", "engineer", "sage"])
def test_both_reply_paths(service, stream, web, role):
    result = service.reply(request(EXPR, web_enabled=web, role=role), "calculator-request-001", stream=stream)
    if stream:
        events = asyncio.run(frames(result))
        assert [event["type"] for event in events] == ["meta", "delta", "done"]
        result = {**events[0], **events[-1], "text": events[1]["text"]}
    assert result["role"] == (role or "companion")
    assert result["answer_verified"] is True
    assert result["calculation"]["exact"] == "4610910773116753869545459649956672820779/27929639013578179724"
    assert result["calculation"]["decimal"] == "165090238755865370728.216339891147987977342708"
    assert result["provider_called"] is False and result["model_cost_usd"] == 0
    assert result["web_used"] is False and result["web_sources"] == []
    assert result["usage_reported_by_provider"] is False
    assert result["model_id"] == "exact-arithmetic-v1"
    assert service.ledger.summary()["counts"] == {"completed": 1}
    assert service.ledger.summary()["model_cost_usd"] == 0


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("text", ["1/0", "2^1000000", "1+", "9" * 101 + "+1"])
def test_error_never_claims_verified(service, stream, text):
    result = service.reply(request(text), "calculator-invalid-001", stream=stream)
    if stream:
        events = asyncio.run(frames(result))
        result = {**events[0], **events[-1], "text": events[1]["text"]}
    assert result["answer_verified"] is False
    assert result["verification_method"] is None
    assert result["calculation"] is None
    assert result["text"].startswith("Calculation not performed:")
    assert result["provider_called"] is False


def test_preview_has_no_execution_or_reservation(service):
    preview = service.preview(request())
    assert preview["reserved_model_cost_usd"] == 0
    assert preview["provider_called"] is False
    assert "answer_verified" not in preview
    assert service.ledger.summary()["counts"] == {}
    assert service.memory.rows == []


def test_non_arithmetic_keeps_existing_chat_path(service):
    assert service.reply(request("Explain the code in this file"), "ordinary-request-001") is None
    assert service.ledger.summary()["counts"] == {}


def test_shared_idempotency_protects_history(service):
    req = request(conversation_id="conversation-present")
    service.reply(req, "one-calculation-id")
    assert len(service.memory.rows) == 2
    with pytest.raises(HTTPException) as error:
        service.reply(req, "one-calculation-id", stream=True)
    assert error.value.status_code == 409
    assert len(service.memory.rows) == 2
    with pytest.raises(HTTPException) as error:
        service.reply(request("2+2"), "one-calculation-id")
    assert error.value.status_code == 409


def test_busy_gate_is_respected_and_released(service):
    service.gate.acquire()
    service.gate.acquire()
    with pytest.raises(HTTPException) as error:
        service.reply(request(), "busy-calculator-id")
    assert error.value.status_code == 429
    service.gate.release()
    service.gate.release()
    assert service.reply(request(), "busy-calculator-id")["answer_verified"]


@pytest.mark.parametrize("field", ["project_id", "conversation_id"])
def test_missing_context_is_rejected(service, field):
    with pytest.raises(HTTPException) as error:
        service.reply(request(**{field: "missing-context"}), "missing-context-id")
    assert error.value.status_code == 404
    assert service.ledger.summary()["counts"] == {}


def test_history_failure_redacted_and_gate_released(service):
    def fail(*args):
        raise RuntimeError("private-history-path-secret")
    service.memory.save_message = fail
    with pytest.raises(HTTPException) as error:
        service.reply(request(conversation_id="conversation-present"), "history-failed-id")
    assert error.value.status_code == 500
    assert "private-history" not in str(error.value)
    assert service.ledger.summary()["counts"] == {"failed_cost_uncertain": 1}
    assert service.gate.acquire(blocking=False)
    assert service.gate.acquire(blocking=False)
    service.gate.release()
    service.gate.release()


def test_unconsumed_stream_does_not_hold_worker(service):
    service.reply(request(), "unconsumed-response-id", stream=True)
    assert service.gate.acquire(blocking=False)
    assert service.gate.acquire(blocking=False)
    service.gate.release()
    service.gate.release()


def test_exhausted_budget_still_rejected(service):
    service.ledger.reserve("earlier-cost-id", "fingerprint", "companion", "old-model", 1, 10_000_000)
    service.monthly_limit = 0
    with pytest.raises(HTTPException) as error:
        service.reply(request(), "budget-rejected-id")
    assert error.value.status_code == 402
    assert service.gate.acquire(blocking=False)
    service.gate.release()
