"""Offline UI contract/syntax checks; browser smoke is a separate validation gate."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_ui_has_review_honest_states_privacy_and_mobile_access():
    js = (ROOT / 'helix/static/follow_through.js').read_text(encoding='utf-8')
    html = (ROOT / 'helix/static/index.html').read_text(encoding='utf-8')
    css = (ROOT / 'helix/static/follow_through.css').read_text(encoding='utf-8')
    for value in ['showModal()', 'expected_version', 'crypto.randomUUID()', 'reviewed',
                  'reported by you', 'No email access', 'source_sha256', 'data.counts',
                  'textContent', 'value', 'has_more']:
        assert value in js
    assert 'localStorage' not in js
    assert 'follow-through-mobile' in html
    assert 'var(--text)' in css and 'focus-visible' in css
    assert 'max-width:650px' in css


def test_chat_hooks_require_explicit_selection_and_do_not_start_contextless_jobs():
    js = (ROOT / 'helix/static/app.js').read_text(encoding='utf-8')
    assert 'payload.outcome_id = selectedOutcome' in js
    assert 'window.helixFollowThrough?.capture(text, sourceConversation)' in js
    assert '&& !window.helixFollowThrough?.activeId()' in js
    assert 'window.helixFollowThrough?.clear()' in js


def test_follow_through_javascript_syntax():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is not installed; syntax check remains a CI/browser gate')
    subprocess.run([node, '--check', str(ROOT / 'helix/static/follow_through.js')],
                   check=True, capture_output=True, text=True, timeout=10)
