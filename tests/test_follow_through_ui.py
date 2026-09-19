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


def test_startup_restore_preserves_open_tracker_but_switch_clears_it():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node required for the real conversation-restore function regression')
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('async function loadConversationById(');
const end = source.indexOf('async function loadConversation()', start);
assert.ok(start >= 0 && end > start);
let clears = 0;
const context = vm.createContext({
  runtimeFeatures: {persistent_conversations: true}, conversationId: 'existing',
  api: async path => ({conversation: {id: path.split('/').pop()}}),
  window: {helixFollowThrough: {clear: () => {clears += 1;}}, localStorage: {setItem() {}}},
  renderConversationMessages() {}, refreshAttachments: async () => {},
  refreshConversationList: async () => {}, toast() {}
});
vm.runInContext(source.slice(start, end), context);
(async () => {
  await context.loadConversationById('existing', false);
  assert.equal(clears, 0, 'Startup must preserve a tracker opened before restoration finishes');
  await context.loadConversationById('different', true);
  assert.equal(clears, 1, 'An actual conversation switch must clear selected private context');
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    subprocess.run([node, '-e', harness, str(ROOT / 'helix/static/app.js')],
                   check=True, capture_output=True, text=True, timeout=10)
