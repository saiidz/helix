from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from helix.core import Profile, Role, Settings
from helix.server import create_app


KEY = "test-product-routing-key-123456789"


def settings():
    return Settings(
        profiles=[
            Profile(role=Role.COMPANION, kind="demo", model_id="demo-companion"),
            Profile(role=Role.ENGINEER, kind="demo", model_id="demo-engineer"),
            Profile(role=Role.SAGE, kind="demo", model_id="demo-sage"),
        ],
        monthly_budget_usd=Decimal("10"),
        task_budget_usd=Decimal("1"),
    )


def test_server_web_auto_uses_live_research_for_fresh_question(tmp_path, monkeypatch):
    calls = []

    def fake_research(query, search_limit=5, fetch_limit=2):
        calls.append(query)
        result = SimpleNamespace(
            title="Official release",
            url="https://example.com/release",
            snippet="A current release note",
        )
        document = SimpleNamespace(
            title="Official release",
            url=result.url,
            text="Current release details",
        )
        return [result], [document]

    monkeypatch.setattr("helix.server.research_web", fake_research)
    app = create_app(settings(), KEY, tmp_path / "ledger.sqlite3")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/route",
            headers={"Authorization": "Bearer " + KEY},
            json={
                "messages": [{"role": "user", "content": "What is the latest Python release?"}],
                "web_mode": "auto",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert calls == ["What is the latest Python release?"]
        assert data["web_enabled"] is True
        assert data["web_sources"][0]["url"] == "https://example.com/release"


def test_web_off_overrides_freshness_heuristic(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "helix.server.research_web",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("web must stay off")),
    )
    app = create_app(settings(), KEY, tmp_path / "ledger.sqlite3")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/route",
            headers={"Authorization": "Bearer " + KEY},
            json={
                "messages": [{"role": "user", "content": "What is the latest Python release?"}],
                "web_mode": "off",
            },
        )
        assert response.status_code == 200
        assert response.json()["web_enabled"] is False


def test_typo_date_chat_stream_bypasses_web_and_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "helix.server.research_web",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("date utility must not browse")),
    )
    monkeypatch.setattr(
        "helix.server.stream_complete",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("date utility must not call model")),
    )
    app = create_app(settings(), KEY, tmp_path / "ledger-date.sqlite3")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/chat/stream",
            headers={
                "Authorization": "Bearer " + KEY,
                "Idempotency-Key": "typo-date-routing-0001",
            },
            json={
                "messages": [{"role": "user", "content": "wha date is it today"}],
                "web_mode": "auto",
            },
        )
        assert response.status_code == 200, response.text
        events = [__import__("json").loads(line) for line in response.text.splitlines() if line.strip()]
        assert [event["type"] for event in events] == ["meta", "delta", "done"]
        assert events[0]["model_id"] == "helix/host-clock"
        assert events[0]["provider_mode"] == "local_utility"
        assert events[0]["provider_called"] is False
        assert events[0]["web_sources"] == []
        assert events[-1]["answer_verified"] is True
        assert events[-1]["verification_method"] == "host_clock"
        assert "September" in events[1]["text"] or any(
            month in events[1]["text"]
            for month in (
                "January", "February", "March", "April", "May", "June",
                "July", "August", "October", "November", "December"
            )
        )


def test_clock_route_wins_before_web_or_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "helix.server.research_web",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("clock should not browse")),
    )
    app = create_app(settings(), KEY, tmp_path / "ledger.sqlite3")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/route",
            headers={"Authorization": "Bearer " + KEY},
            json={
                "messages": [{"role": "user", "content": "what time is it now"}],
                "web_mode": "auto",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == "helix/host-clock"
        assert data["provider_called"] is False
        assert data["web_sources"] == []
