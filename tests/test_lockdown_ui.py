from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_emergency_lockdown_is_visible_in_main_app():
    index = (ROOT / "helix" / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "helix" / "static" / "engineer_jobs.js").read_text(encoding="utf-8")
    style = (ROOT / "helix" / "static" / "engineer_jobs.css").read_text(encoding="utf-8")
    assert 'id="emergency-lockdown-global"' in index
    assert '"/lockdown"' in script
    assert "RESET_HELIX_LOCKDOWN.cmd" in script
    assert "setLockdownUI" in script
    assert ".emergency-lockdown-global" in style


def test_local_lock_and_reset_scripts_are_separate():
    lock = (ROOT / "EMERGENCY_LOCKDOWN.cmd").read_text(encoding="utf-8")
    reset = (ROOT / "RESET_HELIX_LOCKDOWN.cmd").read_text(encoding="utf-8")
    assert "-m helix.safety lock" in lock
    assert "-m helix.safety unlock" in reset
    assert "interactive" in reset.lower()
    assert "-m helix.safety unlock" not in lock
