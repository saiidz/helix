"""Developer-only browser check. Requires optional Playwright + Chromium.

Starts a loopback demo server, checks desktop/mobile, saves evidence, then stops it.
No real model or external service is contacted.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright


def main():
    root=Path(__file__).resolve().parents[1]
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    key='local-ui-fixture-only-not-a-production-key'
    env={**os.environ,'HELIX_API_KEY':key}
    result={'mode':'demo','real_model_used':False,'external_requests':[],'checks':[]}
    with tempfile.TemporaryDirectory() as tmp:
        proc=subprocess.Popen([sys.executable,'-m','helix','--port',str(port),'--ledger',str(Path(tmp)/'ui.sqlite3')],
                              cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            url=f'http://127.0.0.1:{port}'
            for _ in range(80):
                try:
                    with urlopen(url+'/health',timeout=1) as resp:
                        if resp.status==200: break
                except Exception:
                    time.sleep(.1)
            else: raise RuntimeError('Loopback server did not become ready')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True, executable_path=os.environ.get("HELIX_TEST_CHROMIUM") or shutil.which("chromium"))
                page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
                errors=[]
                page.on('pageerror',lambda err:errors.append(str(err)))
                page.on('request',lambda req: result['external_requests'].append(req.url) if not req.url.startswith(url+'/') else None)
                page.goto(url,wait_until='networkidle')
                page.locator('#key').fill(key)
                page.locator('#status').click()
                page.wait_for_function("document.getElementById('connection').textContent.includes('Companion: demo')")
                page.locator('#prompt').fill('Help me debug a Python function.')
                page.locator('#send').click()
                page.wait_for_selector('.message.assistant')
                assert 'Engineer' in page.locator('.message.assistant').inner_text()
                assert 'demo' in page.locator('.message.assistant').inner_text().lower()
                assert page.locator('#error').inner_text()==''
                assert not errors,errors
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.locator('#key').fill('')  # No credentials in evidence, even fixture keys.
                page.screenshot(path=str(root/'evidence'/'ui-desktop.png'),full_page=True)
                result['checks'].append('Desktop: authentication, role routing, demo reply, cost labels, no JS errors, no horizontal overflow')
                page.set_viewport_size({'width':390,'height':844})
                page.goto(url,wait_until='networkidle')
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                assert page.locator('#messages .message').count()==1
                page.screenshot(path=str(root/'evidence'/'ui-mobile.png'),full_page=True)
                result['checks'].append('Mobile 390px: no horizontal overflow; reloading clears displayed conversation')
                assert not result['external_requests'],result['external_requests']
                result['checks'].append('All browser requests stayed on the loopback demo origin')
                browser.close()
            result['status']='passed'
            (root/'evidence'/'ui-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result,indent=2))
        except Exception as exc:
            result['status']='blocked_or_failed'
            result['error']=str(exc)
            (root/'evidence'/'ui-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
            raise
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)


if __name__=='__main__': main()
