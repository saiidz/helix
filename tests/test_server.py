from datetime import date, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from helix.core import Profile,Settings
from helix.providers import Completion,ProviderError
from helix.server import create_app

KEY="test-only-key-not-a-secret-12345678"
BASE=Path(__file__).resolve().parents[1]
HEADERS={"Authorization":f"Bearer {KEY}","Idempotency-Key":"request-id-0000001"}
PAYLOAD={"messages":[{"role":"user","content":"Write Python code"}]}


def client(tmp_path,settings=None):
    return TestClient(create_app(settings or Settings.from_file(BASE/"config/demo.json"),KEY,tmp_path/"l.db",["testserver"]))


def test_demo_end_to_end(tmp_path):
    c=client(tmp_path)
    response=c.post("/api/chat",headers=HEADERS,json=PAYLOAD)
    assert response.status_code == 200, response.text
    data=response.json()
    assert data["role"] == "engineer"
    assert data["provider_mode"] == "demo"
    assert data["actions_executed"] == []
    assert not data["answer_verified"]
    assert "No AI model was called" in data["text"]
    assert c.post("/api/chat",headers=HEADERS,json=PAYLOAD).status_code == 409


def test_auth_required(tmp_path):
    c=client(tmp_path)
    assert c.get("/api/meter").status_code == 401
    assert c.post("/api/chat",json=PAYLOAD).status_code == 401


def test_token_length_validation(tmp_path):
    with pytest.raises(ValueError):
        create_app(Settings.from_file(BASE/"config/demo.json"),"weak",tmp_path/"l.db")


def test_cross_origin_and_dns_rebinding(tmp_path):
    c=client(tmp_path)
    assert c.get("/api/meter",headers={**HEADERS,"Origin":"https://evil.invalid"}).status_code == 403
    assert c.get("/health",headers={"Host":"evil.invalid"}).status_code == 400


def test_oversize_payload(tmp_path):
    c=client(tmp_path)
    assert c.post("/api/chat",headers=HEADERS,content=b"x"*64001).status_code == 413


def test_context_and_task_budget_limits(tmp_path):
    s=Settings.from_file(BASE/"config/demo.json")
    s.profiles[1].context_tokens=1024
    c=client(tmp_path,s)
    large={"messages":[{"role":"user","content":"code "+"x"*4000}]}
    assert c.post("/api/chat",headers=HEADERS,json=large).status_code == 413


def test_route_preview_never_calls_provider(tmp_path,monkeypatch):
    def fail(*args): raise AssertionError("Should not call provider")
    monkeypatch.setattr("helix.server.complete",fail)
    c=client(tmp_path)
    r=c.post("/api/route",headers=HEADERS,json=PAYLOAD)
    assert r.status_code == 200
    assert r.json()["provider_called"] is False


def cloud_settings(expired=False, enabled=False):
    profiles=[Profile(role=role,kind="cloud",model_id="test",base_url="https://api.example.com/v1",
                      price_valid_until=date.today()+timedelta(days=-1 if expired else 1),
                      contract_verified=True) for role in ("companion","engineer","sage")]
    return Settings(profiles=profiles,approved_cloud_hosts=["api.example.com"],allow_external=enabled)


def test_local_only_cannot_escape(tmp_path,monkeypatch):
    def fail(*args): raise AssertionError("Must not call cloud")
    monkeypatch.setattr("helix.server.complete",fail)
    for enabled in (False,True):
        c=client(tmp_path,cloud_settings(enabled=enabled))
        assert c.post("/api/chat",headers=HEADERS,json=PAYLOAD).status_code == 403


def test_request_consent_alone_is_insufficient(tmp_path):
    c=client(tmp_path,cloud_settings(enabled=False))
    assert c.post("/api/chat",headers=HEADERS,json={**PAYLOAD,"allow_external":True}).status_code == 403


def test_stale_cloud_pricing_blocks_call(tmp_path):
    c=client(tmp_path,cloud_settings(expired=True,enabled=True))
    assert c.post("/api/chat",headers=HEADERS,json={**PAYLOAD,"allow_external":True}).status_code == 403


def test_provider_error_not_retried_and_cost_held(tmp_path,monkeypatch):
    calls=[]
    def fail(*args):
        calls.append(1)
        raise ProviderError("simulated timeout")
    monkeypatch.setattr("helix.server.complete",fail)
    c=client(tmp_path)
    assert c.post("/api/chat",headers=HEADERS,json=PAYLOAD).status_code == 502
    assert c.post("/api/chat",headers=HEADERS,json=PAYLOAD).status_code == 409
    assert len(calls)==1
    assert c.get("/api/meter",headers=HEADERS).json()["counts"]["failed_cost_uncertain"]==1


def test_model_endpoint_and_policy(tmp_path):
    c=client(tmp_path)
    assert len(c.get("/api/models",headers=HEADERS).json()["profiles"])==3
    assert c.get("/api/policy/deploy",headers=HEADERS).json()["executed"] is False
    assert "frame-ancestors 'none'" in c.get("/").headers["Content-Security-Policy"]
