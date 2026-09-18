"""Render static local assets without network or a server. Not an integration test."""
from __future__ import annotations
import json
import os
import re
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
html=(root/'helix/static/index.html').read_text()
html=re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
html=re.sub(r'<link\b[^>]*>', '', html)
css=(root/'helix/static/style.css').read_text()
result={'kind':'offline static rendering only', 'javascript_actions_tested':False, 'checks':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path=os.environ.get('HELIX_TEST_CHROMIUM') or shutil.which('chromium'))
    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
    page.set_content(html)
    page.add_style_tag(content=css)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(root/'evidence/ui-desktop.png'),full_page=True)
    result['checks'].append('Desktop static layout: no horizontal overflow')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(root/'evidence/ui-mobile.png'),full_page=True)
    result['checks'].append('Mobile 390px static layout: no horizontal overflow')
    browser.close()
(root/'evidence/ui-preview.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
