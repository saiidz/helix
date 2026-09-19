"""Optional real-browser smoke using synthetic local data and the demo provider.

Run with the pinned requirements-browser.txt. Uses installed Chrome when available;
otherwise requires a Playwright Chromium installation. Never invokes a paid model.
"""
from __future__ import annotations

import json
import shutil
import socket
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from playwright.sync_api import expect, sync_playwright

from helix.core import Settings
from helix.memory import MemoryStore
from helix.server import create_app

ROOT = Path(__file__).resolve().parents[1]
KEY = 'browser-fixture-only-not-a-production-secret-123456'
OUTPUT = ROOT / '.ci-artifacts' / 'follow-through'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        memory = MemoryStore(folder / 'memory.sqlite3')
        conversation = memory.create_conversation('Synthetic client approval')
        memory.save_message(conversation['id'], 'user',
                            'Obtain written approval for the proposal. Ask before sending anything.')
        app = create_app(Settings.from_file(ROOT / 'config/demo.json'), KEY, folder / 'ledger.db')
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline:
                raise RuntimeError('Local fixture server did not start')
            time.sleep(.02)
        try:
            with sync_playwright() as p:
                executable = shutil.which('google-chrome') or shutil.which('chromium')
                browser = p.chromium.launch(headless=True, executable_path=executable,
                                            args=['--no-sandbox'])
                try:
                    page = browser.new_page(viewport={'width': 1440, 'height': 1050})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.add_init_script('sessionStorage.setItem("helixLocalKey", ' + json.dumps(KEY) + ');'
                                         'localStorage.setItem("helixConversationId", ' + json.dumps(conversation['id']) + ');'
                                         'localStorage.setItem("helixWebMode", "off");')
                    page.goto(f'http://127.0.0.1:{port}')
                    page.locator('.follow-track').first.click()
                    expect(page.locator('#follow-through-dialog')).to_be_visible()
                    expect(page.locator('[name="source_text"]')).to_have_attribute('readonly', '')
                    page.locator('[name="title"]').fill('Client proposal approval')
                    page.locator('[name="success_criteria"]').fill('Client confirms written approval for revision two')
                    page.locator('[name="next_action"]').fill('Prepare a follow-up for review; do not send')
                    page.locator('[name="waiting_on"]').fill('Client')
                    page.locator('[name="reviewed"]').check()
                    page.locator('.follow-form button[type="submit"]').click()
                    expect(page.locator('#follow-detail h3')).to_have_text('Client proposal approval')
                    expect(page.locator('[name="note"]')).to_be_visible()
                    checks.append('Reviewed saved-message capture and provenance')
                    page.locator('[name="state"]').select_option('waiting')
                    page.locator('[name="next_action"]').fill('Review any requested changes before following up')
                    page.locator('[name="note"]').fill('Client has acknowledged receipt, not approved the proposal')
                    page.locator('.follow-form button[type="submit"]').click()
                    expect(page.locator('[name="note"]')).to_have_value('')
                    expect(page.locator('[data-view="waiting"]')).to_have_attribute('aria-pressed', 'true')
                    checks.append('Reviewed correction and waiting state; acknowledgment is not resolution')
                    page.screenshot(path=str(OUTPUT / 'dark-desktop.png'))
                    page.evaluate('document.documentElement.dataset.theme = "light"')
                    page.screenshot(path=str(OUTPUT / 'light-desktop.png'))
                    checks.append('Dark and light desktop render')
                    page.reload()
                    page.locator('#follow-through-nav').click()
                    page.locator('[data-view="waiting"]').click()
                    page.locator('.follow-card').filter(has_text='Client proposal approval').click()
                    expect(page.locator('[name="next_action"]')).to_have_value('Review any requested changes before following up')
                    page.locator('.follow-source summary').click()
                    expect(page.locator('.follow-source')).to_contain_text('Revision 2')
                    expect(page.locator('.follow-source')).to_contain_text('Selected saved user message')
                    checks.append('Reload persistence and source/revision history')
                    page.locator('.follow-source summary').click()
                    page.locator('[name="state"]').select_option('resolved_by_user')
                    page.locator('[name="note"]').fill('I personally received approval. This is not independent verification.')
                    page.locator('.follow-form button[type="submit"]').click()
                    expect(page.locator('#follow-detail')).to_contain_text('Resolved — reported by you')
                    expect(page.get_by_role('button', name='Reopen', exact=True)).to_be_visible()
                    checks.append('User-reported closure is labeled honestly')
                    page.get_by_role('button', name='Use in chat', exact=True).click()
                    expect(page.locator('#active-outcome-chip')).to_be_visible()
                    page.locator('#new-chat').click()
                    expect(page.locator('#active-outcome-chip')).to_be_hidden()
                    checks.append('Explicit context selection and new-chat clearing')
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.locator('#follow-through-mobile').click()
                    page.locator('[data-view="closed"]').click()
                    page.locator('.follow-card').filter(has_text='Client proposal approval').click()
                    page.screenshot(path=str(OUTPUT / 'dark-mobile.png'))
                    page.evaluate('document.documentElement.dataset.theme = "light"')
                    page.screenshot(path=str(OUTPUT / 'light-mobile.png'))
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal viewport overflow'
                    assert page.locator('#follow-through-dialog').evaluate('(el) => el.scrollWidth <= el.clientWidth'), 'Dialog overflow'
                    checks.append('390px mobile access and no horizontal overflow')
                    assert not errors, errors
                    checks.append('No uncaught browser errors')
                    (OUTPUT / 'report.json').write_text(json.dumps({'passed': checks,
                        'provider': 'demo; no live inference', 'external_actions': False}, indent=2), encoding='utf-8')
                    print('Browser smoke passed:', len(checks), 'checks')
                finally:
                    browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            sock.close()


if __name__ == '__main__':
    main()
