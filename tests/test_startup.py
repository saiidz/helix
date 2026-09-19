from __future__ import annotations

import copy
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
from types import SimpleNamespace

import pytest

from tools import check_startup as s

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return {"profiles": [
        {"role": role, "kind": "local", "model_id": "fixture-model",
         "base_url": "http://127.0.0.1:11434/v1"}
        for role in ("companion", "engineer", "sage")
    ]}


@pytest.fixture
def model_server():
    state = {"status": 200, "body": b'{"data":[{"id":"fixture-model"}]}', "requests": []}
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"].append((self.path, dict(self.headers)))
            self.send_response(state["status"])
            self.send_header("Location", "http://203.0.113.1/do-not-follow")
            self.end_headers()
            self.wfile.write(state["body"])
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    state["port"] = server.server_port
    yield state
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_configured_port_path_and_ipv6(config):
    config["profiles"][1]["base_url"] = "http://[::1]:8081/custom/v1/"
    endpoints = s.local_endpoints(config)
    assert (endpoints[0].port, endpoints[0].path) == (11434, "/v1/models")
    assert (endpoints[1].host, endpoints[1].port, endpoints[1].path) == ("::1", 8081, "/custom/v1/models")


@pytest.mark.parametrize("base", [
    "https://127.0.0.1/v1", "http://example.com/v1", "http://192.168.1.1/v1",
    "http://169.254.169.254/", "http://localhost:8080/v1", "http://user:secret@127.0.0.1/v1",
    "http://127.0.0.1/v1?key=secret", "http://127.0.0.1/v1#fragment",
    "http://127.0.0.1:0/v1", "http://127.0.0.1:65536/v1", "http://127.0.0.1:bad/v1",
    "http://127.0.0.1/v1\nInjected: header", "http://[invalid/v1", None,
])
def test_reject_invalid_or_external_endpoints(config, base):
    config["profiles"][0]["base_url"] = base
    with pytest.raises(s.StartupError):
        s.local_endpoints(config)


@pytest.mark.parametrize("value", [None, "", "REPLACE_WITH_YOUR_INSTALLED_CHAT_MODEL", "x" * 129, "key\nvalue"])
def test_reject_missing_or_placeholder_models(config, value):
    config["profiles"][0]["model_id"] = value
    with pytest.raises(s.StartupError):
        s.local_endpoints(config)


@pytest.mark.parametrize("kind", ["cloud", "demo"])
def test_no_cloud_or_demo_probes(config, kind):
    config["profiles"][0]["kind"] = kind
    with pytest.raises(s.StartupError):
        s.local_endpoints(config)


def test_exact_roles_required(config):
    config["profiles"][0]["role"] = "engineer"
    with pytest.raises(s.StartupError):
        s.local_endpoints(config)
    with pytest.raises(s.StartupError):
        s.local_endpoints({"profiles": []})


def test_read_config_private_errors_and_bounds(tmp_path, capsys):
    path = tmp_path / "local.json"
    for raw in [b'{"PRIVATE_SECRET', b'[]', b'\xff', b' ' * (s.MAX_BYTES + 1)]:
        path.write_bytes(raw)
        with pytest.raises(s.StartupError) as error:
            s.read_config(path)
        assert "PRIVATE_SECRET" not in str(error.value)
    path.unlink()
    with pytest.raises(s.StartupError):
        s.read_config(path)
    path.write_text('{"profiles": []}')
    assert s.read_config(path) == {"profiles": []}
    assert not capsys.readouterr().out


def test_loopback_probe_deduplicates_and_ignores_proxy(config, model_server, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://203.0.113.1:1234")
    for profile in config["profiles"]:
        profile["base_url"] = f'http://127.0.0.1:{model_server["port"]}/custom/v1'
    s.check_models(s.local_endpoints(config))
    assert len(model_server["requests"]) == 1
    path, headers = model_server["requests"][0]
    assert path == "/custom/v1/models"
    assert "Authorization" not in headers


@pytest.mark.parametrize("status,body", [
    (302, b'{}'), (500, b'{}'), (200, b'not json'), (200, b'{"data":[]}'),
    (200, b'{"data":[{}]}'), (200, b'{"data":[{"id":12}]}'),
    (200, b'null'), (200, b'x' * (s.MAX_BYTES + 1)),
])
def test_bad_model_responses_never_pass_or_follow_redirects(model_server, status, body):
    model_server.update(status=status, body=body)
    with pytest.raises(s.StartupError):
        s.fetch_model_ids(s.Endpoint("companion", "127.0.0.1", model_server["port"], "/v1/models", "fixture-model"))
    assert len(model_server["requests"]) == 1


def test_wrong_model_id_is_not_ready(config, model_server):
    for profile in config["profiles"]:
        profile["base_url"] = f'http://127.0.0.1:{model_server["port"]}/v1'
    config["profiles"][0]["model_id"] = "PRIVATE_MODEL_NAME"
    with pytest.raises(s.StartupError) as error:
        s.check_models(s.local_endpoints(config))
    assert "PRIVATE_MODEL_NAME" not in str(error.value)


def test_direct_probe_cannot_bypass_loopback_guard():
    with pytest.raises(s.StartupError):
        s.fetch_model_ids(s.Endpoint("companion", "203.0.113.1", 80, "/v1/models", "x"))


def test_occupied_port_and_invalid_port_fail():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(s.StartupError, match="Stop only the old HELIX"):
            s.check_port(port)
    s.check_port(port)
    with pytest.raises(s.StartupError):
        s.check_port(80)


def test_import_errors_do_not_print_private_values(monkeypatch):
    def broken(name):
        raise RuntimeError("PRIVATE_VALUE")
    monkeypatch.setattr(s.importlib, "import_module", broken)
    with pytest.raises(s.StartupError) as error:
        s.check_imports_and_schema({})
    assert "PRIVATE_VALUE" not in str(error.value)


def fixture_checkout(tmp_path, config):
    for name in s.REQUIRED_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    path = tmp_path / "config/local.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(config))
    return path


def test_offline_really_makes_no_network_call(tmp_path, config, monkeypatch, capsys):
    path = fixture_checkout(tmp_path, config)
    monkeypatch.setattr(s.sys, "version_info", (3, 13))
    monkeypatch.setattr(s, "check_imports_and_schema", lambda data: None)
    def forbidden(*args):
        pytest.fail("Offline preflight must not probe ports or models")
    monkeypatch.setattr(s, "check_port", forbidden)
    monkeypatch.setattr(s, "check_models", forbidden)
    assert s.run_checks(tmp_path, path, offline=True, port=8765) == 0
    assert "NOT checked" in capsys.readouterr().out


def test_failure_names_stage_and_returns_nonzero(tmp_path, config, monkeypatch, capsys):
    path = fixture_checkout(tmp_path, config)
    monkeypatch.setattr(s.sys, "version_info", (3, 13))
    (tmp_path / "START_HELIX_AGENT.cmd").unlink()
    assert s.run_checks(tmp_path, path, offline=True, port=8765) == 1
    assert "FAIL [checkout files]" in capsys.readouterr().out
    monkeypatch.setattr(s.sys, "version_info", (3, 12))
    assert s.run_checks(tmp_path, path, offline=True, port=8765) == 1
    assert "FAIL [Python]" in capsys.readouterr().out


def test_tracked_private_files_gate_uses_real_git(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    s.check_tracked_private(tmp_path)
    path = tmp_path / "config/local.json"
    path.parent.mkdir()
    path.write_text("PRIVATE_VALUE")
    subprocess.run(["git", "add", "config/local.json"], cwd=tmp_path, check=True)
    with pytest.raises(s.StartupError) as error:
        s.check_tracked_private(tmp_path)
    assert "PRIVATE_VALUE" not in str(error.value)
    assert path.read_text() == "PRIVATE_VALUE"


def test_real_application_imports_and_schema(config):
    # Full repository / CI integration, not a mocked launcher.
    s.check_imports_and_schema(config)


def test_batch_update_gate_is_explicit_and_non_destructive():
    text = (ROOT / "DEV_LOOP_WINDOWS.cmd").read_text()
    assert "git pull --ff-only origin feat/codex-inspired-ui-v02" in text
    assert "-m tools.intelligence_eval" in text
    assert "--offline --tracked-private" in text
    assert "FAILED STAGE:" in text
    assert "-m pytest -q" in text
    assert "-m compileall -q helix tests tools" in text
    assert "8080" not in text
    for command in ("git reset", "git stash", "git clean", "git push", "--force", "taskkill"):
        assert command not in text


@pytest.mark.skipif(os.name != "nt", reason="Native cmd.exe exit propagation requires Windows")
@pytest.mark.parametrize("code", [0, 7])
def test_native_main_launcher_preserves_child_exit_code(tmp_path, code):
    root = tmp_path / "path with spaces"
    (root / ".venv/Scripts").mkdir(parents=True)
    (root / ".venv/Scripts/python.exe").touch()  # existence check only; never executed
    (root / "config").mkdir()
    (root / "config/local.json").write_text("{}")
    shutil.copyfile(ROOT / "START_HELIX.cmd", root / "START_HELIX.cmd")
    (root / "START_HELIX_AUTO.cmd").write_text(f"@exit /b {code}\n")
    result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", "START_HELIX.cmd"],
                            cwd=root, env={**os.environ, "HELIX_NO_PAUSE": "1"},
                            capture_output=True, timeout=10)
    assert result.returncode == code


@pytest.mark.skipif(os.name != "nt", reason="Native cmd.exe validation requires Windows")
def test_native_missing_python_stops_before_git_or_launch(tmp_path):
    shutil.copyfile(ROOT / "DEV_LOOP_WINDOWS.cmd", tmp_path / "DEV_LOOP_WINDOWS.cmd")
    result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", "DEV_LOOP_WINDOWS.cmd"],
                            cwd=tmp_path, env={**os.environ, "HELIX_NO_PAUSE": "1"},
                            capture_output=True, timeout=10)
    assert result.returncode != 0
    assert b"FAILED STAGE: Python environment" in result.stdout
    assert b"[1/7]" not in result.stdout
