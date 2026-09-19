from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_app_exposes_engineer_jobs_without_inline_handlers():
    index = (ROOT / "helix" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="engineer-jobs-nav"' in index
    assert '/static/engineer_jobs.css' in index
    assert '/static/engineer_jobs.js' in index
    assert 'id="engineer-jobs-cap-label"' in index
    assert "Command execution is still unsandboxed" in index
    assert "onclick=" not in index


def test_engineer_jobs_script_keeps_approval_and_workspace_boundaries_visible():
    script = (ROOT / "helix" / "static" / "engineer_jobs.js").read_text(encoding="utf-8")
    assert '"/status"' in script
    assert '"/start"' in script
    assert '"/decision"' in script
    assert '"/stop"' in script
    assert 'Approve exact action' in script
    assert 'Command execution is not OS-sandboxed yet' in script
    assert 'innerHTML = event' not in script
