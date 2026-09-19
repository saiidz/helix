from pathlib import Path

from fastapi.testclient import TestClient

from helix.core import Profile, Role, Settings
from helix.server import create_app


ROOT = Path(__file__).resolve().parents[1]
KEY = "test-product-ui-key-123456789012345"


def settings():
    return Settings(
        profiles=[
            Profile(role=Role.COMPANION, kind="demo", model_id="demo-companion"),
            Profile(role=Role.ENGINEER, kind="demo", model_id="demo-engineer"),
            Profile(role=Role.SAGE, kind="demo", model_id="demo-sage"),
        ],
    )


def test_main_product_surface_uses_branding_and_separate_admin():
    index = (ROOT / "helix" / "static" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "helix" / "static" / "product.css").read_text(encoding="utf-8")
    assert "/static/branding/helix-logo.svg" in index
    assert "/static/product.css" in index
    assert 'href="/admin"' in index
    assert 'id="emergency-lockdown-global"' not in index
    assert ".intel{display:none" in css
    assert ".composer-zone" in css


def test_main_chat_is_tool_first_and_engineer_aware():
    script = (ROOT / "helix" / "static" / "app.js").read_text(encoding="utf-8")
    assert "verificationLabel" in script
    assert 'payload.web_mode = webMode' in script
    assert "window.helixEngineer?.startFromChat" in script
    assert "looksLikeEngineerWorkspaceTask" in script
    assert "workspace not connected" in script.lower()
    assert '" · unverified"' not in script


def test_engineer_bridge_is_exposed_without_admin_lock_button():
    script = (ROOT / "helix" / "static" / "engineer_jobs.js").read_text(encoding="utf-8")
    assert "window.helixEngineer" in script
    assert "startFromChat" in script
    assert 'id="engineer-lockdown"' not in script
    assert 'href="/admin"' in script


def test_admin_page_is_served_and_has_no_inline_handlers(tmp_path):
    app = create_app(settings(), KEY, tmp_path / "ledger.sqlite3")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/admin")
        assert response.status_code == 200
        assert "OWNER CONTROLS" in response.text
        assert "onclick=" not in response.text


def test_tool_routed_messages_can_be_persisted_without_model(tmp_path):
    app = create_app(settings(), KEY, tmp_path / "ledger.sqlite3")
    headers = {"Authorization": "Bearer " + KEY}
    with TestClient(app, base_url="http://127.0.0.1") as client:
        created = client.post("/api/conversations", headers=headers, json={"title": "Tool routed"}).json()
        conversation_id = created["conversation"]["id"]
        for role, content in (("user", "Read main.py"), ("assistant", "Engineer job started")):
            response = client.post(
                f"/api/conversations/{conversation_id}/messages",
                headers=headers,
                json={"role": role, "content": content},
            )
            assert response.status_code == 200
        loaded = client.get(f"/api/conversations/{conversation_id}", headers=headers).json()["conversation"]
        assert [message["content"] for message in loaded["messages"]][-2:] == [
            "Read main.py",
            "Engineer job started",
        ]
