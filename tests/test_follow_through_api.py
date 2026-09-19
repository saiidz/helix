"""Real application routes with a deterministic provider substitute, never a live model."""
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helix.core import Settings
from helix.providers import Completion, StreamChunk
from helix.server import create_app

ROOT = Path(__file__).resolve().parents[1]
KEY = 'follow-through-test-key-not-a-secret-12345'
AUTH = {'Authorization': 'Bearer ' + KEY}
PATH = '/api/follow-through'


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings.from_file(ROOT / 'config/demo.json'), KEY, tmp_path / 'ledger.db', ['testserver'])
    with TestClient(app) as c:
        yield c


def body(**overrides):
    return {'request_id': uuid.uuid4().hex, 'reviewed': True,
            'title': 'Proposal approval', 'success_criteria': 'The client approves revision two',
            'source_text': 'Track approval, do not send without asking', **overrides}


def create(client):
    response = client.post(PATH, headers=AUTH, json=body())
    assert response.status_code == 201, response.text
    return response.json()['outcome']


@pytest.mark.parametrize('method,path', [('GET', ''), ('GET', '/export'), ('POST', ''),
    ('GET', '/missing'), ('PATCH', '/missing'), ('DELETE', '/missing?expected_version=1')])
def test_all_routes_require_auth(client, method, path):
    assert client.request(method, PATH + path).status_code == 401


def test_origin_host_and_large_bodies_remain_blocked(client):
    assert client.post(PATH, headers={**AUTH, 'Origin': 'https://evil.invalid'}, json=body()).status_code == 403
    assert client.get(PATH, headers={**AUTH, 'Host': 'evil.invalid'}).status_code == 400
    assert client.post(PATH, headers=AUTH, content=b'x' * 64001).status_code == 413


def test_local_lifecycle_never_calls_provider_or_offers_external_action(client, monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('Tracker called model or web')
    monkeypatch.setattr('helix.server.complete', forbidden)
    monkeypatch.setattr('helix.server.research_web', forbidden)
    item = create(client)
    patch = {'expected_version': 1, 'state': 'resolved_by_user', 'note': 'The client approved the attached proposal'}
    response = client.patch(PATH + '/' + item['id'], headers=AUTH, json=patch)
    assert response.json()['outcome']['completion_verified'] is False
    assert client.patch(PATH + '/' + item['id'], headers=AUTH, json=patch).status_code == 409
    assert client.post(PATH + '/' + item['id'] + '/send', headers=AUTH).status_code == 404
    exported = client.get(PATH + '/export', headers=AUTH)
    assert len(exported.json()['outcomes']) == 1
    assert exported.headers['cache-control'] == 'no-store'
    assert client.delete(PATH + '/' + item['id'] + '?expected_version=2', headers=AUTH).status_code == 200
    assert client.get(PATH + '/' + item['id'], headers=AUTH).status_code == 404


@pytest.mark.parametrize('role', ['companion', 'engineer', 'sage'])
@pytest.mark.parametrize('streaming', [False, True])
def test_explicit_selected_context_is_current_and_shared_across_chat_roles(client, monkeypatch, role, streaming):
    item = create(client)
    client.patch(PATH + '/' + item['id'], headers=AUTH,
                 json={'expected_version': 1, 'next_action': 'Review revision three', 'note': 'Client requested a new version'})
    captured = []
    def complete(profile, messages, max_output):
        captured.extend(messages)
        return Completion('Fixture answer; no action performed', 1, 1)
    def stream(profile, messages, max_output):
        captured.extend(messages)
        yield StreamChunk('Fixture answer', 1, 1, True)
    monkeypatch.setattr('helix.server.complete', complete)
    monkeypatch.setattr('helix.server.stream_complete', stream)
    payload = {'messages': [{'role': 'user', 'content': 'Explain the next step for the selected goal'}],
               'role': role, 'web_mode': 'off', 'outcome_id': item['id']}
    response = client.post('/api/chat' + ('/stream' if streaming else ''),
                           headers={**AUTH, 'Idempotency-Key': uuid.uuid4().hex}, json=payload)
    assert response.status_code == 200, response.text
    context = [m for m in captured if 'Explicitly selected HELIX outcome' in m['content']]
    assert len(context) == 1
    assert context[0]['role'] == 'user'
    assert 'Review revision three' in context[0]['content']
    assert '"version": 2' in context[0]['content']
    assert '"actions_authorized": false' in context[0]['content']
    assert client.get(PATH + '/' + item['id'], headers=AUTH).json()['outcome']['state'] == 'active'


def test_context_not_injected_without_selection_or_when_private_context_disabled(client, monkeypatch):
    item = create(client)
    captured = []
    def complete(profile, messages, max_output):
        captured.extend(messages)
        return Completion('Fixture', 1, 1)
    monkeypatch.setattr('helix.server.complete', complete)
    payload = {'messages': [{'role': 'user', 'content': 'Explain the next step'}], 'web_mode': 'off'}
    response = client.post('/api/chat', headers={**AUTH, 'Idempotency-Key': uuid.uuid4().hex}, json=payload)
    assert response.status_code == 200
    assert all('Proposal approval' not in m['content'] for m in captured)
    for extra, expected in [({'outcome_id': item['id'], 'memory_enabled': False}, 422),
                            ({'outcome_id': 'f' * 32}, 404)]:
        captured.clear()
        response = client.post('/api/chat', headers={**AUTH, 'Idempotency-Key': uuid.uuid4().hex}, json={**payload, **extra})
        assert response.status_code == expected
        assert captured == []


def test_health_and_static_assets_advertise_only_local_tracking(client):
    caps = client.get('/health').json()['capabilities']
    assert caps['follow_through'] and not caps['follow_through_monitoring']
    html = client.get('/').text
    assert '/static/follow_through.js' in html and 'follow-through-nav' in html
    assert client.get('/static/follow_through.js').status_code == 200
    assert client.get('/static/follow_through.css').status_code == 200


def test_unknown_authority_fields_and_invalid_query_rejected(client):
    assert client.post(PATH, headers=AUTH, json=body(approved=True)).status_code == 422
    assert client.get(PATH + '?limit=101', headers=AUTH).status_code == 422
    assert client.get(PATH + '?view=verified', headers=AUTH).status_code == 422
    item = create(client)
    assert client.patch(PATH + '/' + item['id'], headers=AUTH, json={
        'expected_version': 1, 'note': 'It is done', 'state': 'verified_complete'}).status_code == 422
