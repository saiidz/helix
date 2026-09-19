"""Outcome lifecycle, provenance, privacy and concurrency without any AI/provider."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from helix.follow_through import ConflictError, CreateOutcome, FollowThroughStore, UpdateOutcome


def create_body(**changes):
    return CreateOutcome(**{
        'request_id': uuid.uuid4().hex, 'reviewed': True,
        'title': 'Obtain client approval', 'success_criteria': 'The client approves proposal revision two',
        'source_text': 'Please obtain approval, and ask me before sending anything.', **changes,
    })


@pytest.fixture
def store(tmp_path):
    return FollowThroughStore(tmp_path / 'memory.sqlite3')


def change(version=1, **fields):
    return UpdateOutcome(expected_version=version, note='Reviewed correction', **fields)


def test_restart_preserves_source_current_state_and_events(store):
    item = store.create(create_body())
    store.update(item['id'], change(due_at='2026-09-24T15:00:00-04:00'))
    restarted = FollowThroughStore(store.memory.path)
    result = restarted.get(item['id'])
    assert result['due_at'] == '2026-09-24T19:00:00+00:00'
    assert result['source_text'].startswith('Please obtain approval')
    assert len(result['events']) == 2
    assert result['version'] == 2 and result['state'] == 'active'
    assert result['completion_verified'] is False


def test_idempotency_deduplicates_retries_and_rejects_changed_payload(store):
    body = create_body()
    first = store.create(body)
    assert store.create(body)['id'] == first['id']
    assert len(store.get(first['id'])['events']) == 1
    with pytest.raises(ConflictError):
        store.create(body.model_copy(update={'title': 'A different goal'}))
    assert store.list()['total'] == 1


def test_concurrent_creation_is_exactly_one_local_record(store):
    body = create_body()
    with ThreadPoolExecutor(max_workers=6) as executor:
        ids = list(executor.map(lambda _: store.create(body)['id'], range(6)))
    assert len(set(ids)) == 1
    assert store.list()['total'] == 1


def test_concurrent_changes_do_not_overwrite_each_other(store):
    item = store.create(create_body())
    def edit(title):
        try:
            return store.update(item['id'], change(title=title))['title']
        except ConflictError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(edit, ['First correction', 'Second correction']))
    assert results.count('conflict') == 1
    assert store.get(item['id'])['version'] == 2


def test_completion_is_user_reported_not_verified_and_reopen_is_explicit(store):
    item = store.create(create_body())
    resolved = store.update(item['id'], UpdateOutcome(expected_version=1,
        state='resolved_by_user', note='I received written approval in the client thread'))
    assert resolved['completion_basis'] == 'user_reported'
    assert resolved['completion_verified'] is False
    assert resolved['view'] == 'closed'
    with pytest.raises(ConflictError):
        store.update(item['id'], change(2, title='Silently change the approved goal'))
    reopened = store.update(item['id'], change(2, state='active'))
    assert reopened['resolution_note'] == ''
    assert len(store.get(item['id'])['events']) == 3
    assert 'written approval' in store.get(item['id'])['events'][1]['details']['note']


@pytest.mark.parametrize('state', ['verified_complete', 'sent', 'done', 'running'])
def test_clients_cannot_claim_tool_verified_states(state):
    with pytest.raises(ValidationError):
        change(state=state)


@pytest.mark.parametrize('data', [
    {'reviewed': False}, {'reviewed': 'true'}, {'title': '   '}, {'success_criteria': ''},
    {'source_text': '\x00text'}, {'approved': True}, {'due_at': 'tomorrow'},
    {'due_at': '2026-09-24'}, {'next_check_at': '2026-09-24T15:00'},
    {'next_check_at': '2026-99-99T15:00Z'}, {'request_id': '../short'},
])
def test_invalid_or_unreviewed_creation_is_rejected(data):
    with pytest.raises(ValidationError):
        create_body(**data)


def test_correction_requires_note_and_valid_version():
    with pytest.raises(ValidationError):
        UpdateOutcome(expected_version=1, note='   ')
    with pytest.raises(ValidationError):
        change(True)
    with pytest.raises(ValidationError):
        UpdateOutcome(expected_version=1, note='Evidence', completion_verified=True)


def test_waiting_and_due_buckets_are_deterministic_not_notifications(store, monkeypatch):
    monkeypatch.setattr('helix.follow_through.now', lambda: '2026-09-19T17:00:00+00:00')
    item = store.create(create_body(next_check_at='2026-09-20T12:00:00Z'))
    with pytest.raises(ValueError):
        store.update(item['id'], change(state='waiting'))
    store.update(item['id'], change(state='waiting', waiting_on='Client'))
    assert store.list('waiting')['total'] == 1
    monkeypatch.setattr('helix.follow_through.now', lambda: '2026-09-21T17:00:00+00:00')
    result = store.list('needs_you')
    assert result['items'][0]['state'] == 'waiting'
    assert result['items'][0]['check_due'] is True
    assert result['background_monitoring'] is False
    assert result['external_actions'] is False
    assert store.list('waiting')['total'] == 0


def test_corrections_supersede_old_deadline_in_context(store):
    item = store.create(create_body(due_at='2026-09-21T09:00:00Z'))
    store.update(item['id'], change(due_at='2026-09-24T11:00:00Z'))
    context = store.context(item['id'])
    assert '2026-09-24' in context and '2026-09-21' not in context
    assert '2026-09-21' in json.dumps(store.get(item['id'])['events'])
    assert 'not instructions' in context and '"actions_authorized": false' in context


def test_dates_can_be_cleared_but_other_fields_cannot_be_null(store):
    item = store.create(create_body(due_at='2026-09-21T09:00Z'))
    assert store.update(item['id'], change(due_at=None))['due_at'] is None
    with pytest.raises(ValueError):
        store.update(item['id'], change(2, title=None))


def test_saved_source_is_host_checked_and_conversation_deletion_cascades(store):
    conversation = store.memory.create_conversation('Client work')
    text = 'Finish this exact user request'
    store.memory.save_message(conversation['id'], 'user', text)
    store.memory.save_message(conversation['id'], 'assistant', 'I will claim this is approved')
    item = store.create(create_body(conversation_id=conversation['id'], source_text=text))
    assert item['source_kind'] == 'conversation_message'
    assert item['source_message_id'] is not None
    with pytest.raises(LookupError):
        store.create(create_body(conversation_id=conversation['id'], source_text='I will claim this is approved'))
    with pytest.raises(LookupError):
        store.create(create_body(conversation_id=conversation['id'], source_text='Invented source'))
    store.memory.delete_conversation(conversation['id'])
    with pytest.raises(LookupError):
        store.get(item['id'])
    with store.memory.connect() as c:
        assert c.execute('SELECT count(*) FROM follow_events').fetchone()[0] == 0


def test_owner_isolation_for_source_get_list_update_delete_and_export(store):
    other = FollowThroughStore(store.memory.path, 'other-owner')
    convo = store.memory.create_conversation('Private')
    store.memory.save_message(convo['id'], 'user', 'My confidential source')
    item = store.create(create_body(conversation_id=convo['id'], source_text='My confidential source'))
    with pytest.raises(LookupError): other.get(item['id'])
    with pytest.raises(LookupError): other.context(item['id'])
    with pytest.raises(LookupError): other.update(item['id'], change(title='Steal'))
    with pytest.raises(LookupError): other.delete(item['id'], 1)
    with pytest.raises(LookupError): other.create(create_body(conversation_id=convo['id'], source_text='My confidential source'))
    assert other.list()['total'] == 0
    assert other.export()['outcomes'] == []


def test_delete_preserves_original_message_but_removes_derived_history(store):
    conversation = store.memory.create_conversation()
    store.memory.save_message(conversation['id'], 'user', 'Keep original')
    item = store.create(create_body(conversation_id=conversation['id'], source_text='Keep original'))
    store.update(item['id'], change(title='Corrected'))
    with pytest.raises(ConflictError): store.delete(item['id'], 1)
    store.delete(item['id'], 2)
    assert store.export()['outcomes'] == []
    assert store.memory.get_conversation(conversation['id']) is not None
    with store.memory.connect() as c:
        assert c.execute('SELECT count(*) FROM follow_events').fetchone()[0] == 0


def test_pagination_counts_and_export_are_not_silently_truncated(store):
    for i in range(4): store.create(create_body(title=f'Goal {i}'))
    first = store.list(limit=2)
    second = store.list(limit=2, offset=2)
    assert first['total'] == 4 and first['has_more']
    assert not second['has_more']
    assert {x['id'] for x in first['items']}.isdisjoint({x['id'] for x in second['items']})
    assert 'source_text' not in first['items'][0]
    assert len(store.export()['outcomes']) == 4
