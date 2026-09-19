from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from helix import core
from helix.core import ChatRequest, Role, make_messages
from helix.runtime_context import runtime_context


EVENING = datetime(2026, 9, 18, 23, 45, tzinfo=timezone(timedelta(hours=-4)))


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("enabled", [False, True])
def test_all_chat_roles_receive_runtime_facts(monkeypatch, role, enabled):
    monkeypatch.setattr(core, "runtime_context", lambda web: runtime_context(web, now=EVENING))
    req = ChatRequest(messages=[{"role": "user", "content": "What is today's date?"}], web_enabled=enabled)
    before = req.model_dump()
    messages = make_messages(role, req)
    system = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "Current date: 2026-09-18" in system
    assert "2026-09-18T23:45:00-04:00" in system
    assert "Model training cutoff: not provided" in system
    assert "trained through today" in system
    assert "only when this request supplies usable Web Research sources" in system
    assert ("enabled for this request" in system) is enabled
    assert req.model_dump() == before
    assert req.allow_external is False
    assert messages[-1]["content"].startswith("/think" if role == Role.SAGE else "/no_think")


@pytest.mark.parametrize("enabled", [False, True])
def test_date_is_recomputed_for_each_turn(monkeypatch, enabled):
    instants = iter([EVENING, EVENING + timedelta(days=1), EVENING.replace(year=2027)])
    monkeypatch.setattr(core, "runtime_context", lambda web: runtime_context(web, now=next(instants)))
    req = ChatRequest(messages=[{"role": "user", "content": "Today's date?"}], web_enabled=enabled)
    for date in ("2026-09-18", "2026-09-19", "2027-09-18"):
        assert f"Current date: {date}" in make_messages(Role.COMPANION, req)[0]["content"]


def test_host_timezone_not_utc_calendar_date():
    assert EVENING.astimezone(timezone.utc).date().isoformat() == "2026-09-19"
    assert "Current date: 2026-09-18" in runtime_context(False, now=EVENING)


def test_real_clock_is_read_when_now_not_supplied(monkeypatch):
    class Clock:
        @staticmethod
        def now(tz):
            assert tz is timezone.utc
            return EVENING
    monkeypatch.setattr("helix.runtime_context.datetime", Clock)
    # astimezone() deliberately uses the host timezone in production.
    expected = EVENING.astimezone().date().isoformat()
    assert f"Current date: {expected}" in runtime_context(False)


def test_web_off_does_not_enable_network():
    text = runtime_context(False, now=EVENING)
    assert "not requested for this turn" in text
    assert "do not browse" in text
    assert "Web Auto or Web On" in text
    assert "not proof of a successful search" in text


def test_enabled_does_not_claim_success_or_training_upgrade():
    text = runtime_context(True, now=EVENING)
    assert "consult the supplied research outcome" in text
    assert "never invent one" in text
    assert "Cached evidence may be stale" in text
    assert "older event" in text
    assert "untrusted data" in text
    assert "permission to run code" in text


def test_old_cutoff_message_does_not_supply_runtime_date(monkeypatch):
    monkeypatch.setattr(core, "runtime_context", lambda web: runtime_context(web, now=EVENING))
    req = ChatRequest(messages=[
        {"role": "assistant", "content": "My training was updated in 2024 and I have no internet."},
        {"role": "user", "content": "What is today's date?"},
    ])
    messages = make_messages(Role.COMPANION, req)
    assert "Current date: 2026-09-18" in messages[0]["content"]
    assert "not training memory or older chat messages" in messages[0]["content"]
    assert messages[1]["content"] == req.messages[0].content


def test_user_cannot_override_clock_with_request_field():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": "Hello"}], current_date="2099-01-01")


@pytest.mark.parametrize("value", [None, "true", "false", 1, 0])
def test_invalid_web_state_is_rejected(value):
    with pytest.raises(TypeError):
        runtime_context(value, now=EVENING)


def test_timezone_ambiguous_clock_is_rejected():
    with pytest.raises(ValueError):
        runtime_context(False, now=datetime(2026, 9, 18))


def test_context_is_bounded():
    assert len(runtime_context(False, now=EVENING)) < 1600
