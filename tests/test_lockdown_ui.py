from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_emergency_lockdown_is_admin_only_in_web_product():
    index = (ROOT / "helix" / "static" / "index.html").read_text(encoding="utf-8")
    admin = (ROOT / "helix" / "static" / "admin.html").read_text(encoding="utf-8")
    admin_script = (ROOT / "helix" / "static" / "admin.js").read_text(encoding="utf-8")
    engineer_script = (ROOT / "helix" / "static" / "engineer_jobs.js").read_text(encoding="utf-8")

    assert 'id="emergency-lockdown-global"' not in index
    assert 'id="lockdown"' in admin
    assert '"/api/engineer-agent/lockdown"' in admin_script
    assert "RESET_HELIX_LOCKDOWN.cmd" in admin
    assert "setLockdownUI" in engineer_script


def test_local_lock_and_reset_scripts_are_separate():
    lock = (ROOT / "EMERGENCY_LOCKDOWN.cmd").read_text(encoding="utf-8")
    reset = (ROOT / "RESET_HELIX_LOCKDOWN.cmd").read_text(encoding="utf-8")
    assert "-m helix.safety lock" in lock
    assert "-m helix.safety unlock" in reset
    assert "interactive" in reset.lower()
    assert "-m helix.safety unlock" not in lock
