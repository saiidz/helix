"""Test naming portability; no model, network, or HELIX execution tools."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


HOOK_PATH = Path(__file__).with_name("conftest.py")


def label(value, name="data"):
    spec = importlib.util.spec_from_file_location("helix_test_id_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.pytest_make_parametrize_id(value, name)


@pytest.mark.parametrize("value", [None, True, 42, 1.5, "short", b"short", "x" * 128])
def test_short_values_keep_default_ids(value):
    assert label(value) is None


def test_long_labels_are_bounded_stable_and_distinct():
    values = [b"x" * 350001, "x" * 350001, "y" * 350001, "\U0001f600" * 350001,
              "\ud800" * 129, b"\x00" * 129]
    labels = [label(value) for value in values]
    assert len(set(labels)) == len(values)
    for value, result in zip(values, labels):
        assert result == label(value)
        assert f"len{len(value)}" in result
        assert len(result) < 100
        assert result.isascii()
    assert len(label(values[0], "argument" * 100)) < 100


# Every child runs only generated test fixtures in its temporary directory.
# Bound the OS environment write as Windows does so Linux catches the regression.
BOOTSTRAP = r'''
import json
import os
from pathlib import Path
import sys
import pytest
original_putenv = os.putenv

def bounded_putenv(key, value):
    key_text, value_text = os.fsdecode(key), os.fsdecode(value)
    if key_text == "PYTEST_CURRENT_TEST":
        units = len((key_text + "=" + value_text).encode("utf-16-le", "surrogatepass")) // 2
        if units > 32767:
            raise ValueError("the environment variable is longer than 32767 characters")
    return original_putenv(key, value)

class PhaseRecorder:
    def __init__(self):
        self.reports = []

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        # Observe the normal report without suppressing or replacing failures.
        outcome = yield
        report = outcome.get_result()
        self.reports.append({
            "phase": report.when,
            "outcome": report.outcome,
            "exception_type": call.excinfo.type.__name__ if call.excinfo else None,
        })

os.putenv = bounded_putenv
recorder = PhaseRecorder()
exit_code = pytest.main(sys.argv[1:], plugins=[recorder])
# Store only phase/type metadata, never the oversized payload or node ID.
Path("pytest-outcomes.json").write_text(json.dumps(recorder.reports), encoding="utf-8")
raise SystemExit(exit_code)
'''

CASES = r'''
import json
import os
from pathlib import Path
import pytest

@pytest.mark.parametrize("data", [b"x" * 350001, "x" * 350001])
def test_full_payload(data, request):
    assert len(data) == 350001
    assert data == (b"x" if isinstance(data, bytes) else "x") * 350001
    assert len(os.environ["PYTEST_CURRENT_TEST"]) < 1000
    with Path("observed.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps({"id": request.node.nodeid, "length": len(data)}) + "\n")

@pytest.mark.parametrize("data", [pytest.param(b"y" * 350001, id="explicit-short-name")])
def test_explicit_id(data, request):
    assert len(data) == 350001
    assert request.node.name.endswith("[explicit-short-name]")

@pytest.fixture(params=[b"z" * 350001])
def payload(request):
    return request.param

def test_parametrized_fixture(payload):
    assert payload == b"z" * 350001
    assert len(os.environ["PYTEST_CURRENT_TEST"]) < 1000

@pytest.mark.parametrize("data", [b"r" * 350001, b"r" * 350001])
def test_repeated_payload_ids(data, request):
    assert len(data) == 350001
    assert len(request.node.nodeid) < 1000
'''


def run_child(directory: Path, *arguments: str):
    env = os.environ.copy()
    # Isolate only this nested runner from unrelated developer plugins/options.
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST"):
        env.pop(key, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return subprocess.run(
        [sys.executable, "-c", BOOTSTRAP, "-q", "--tb=no", "--maxfail=1", *arguments],
        cwd=directory, env=env, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30,
    )


def test_reproducer_with_windows_limit_and_original_payloads(tmp_path):
    case_file = tmp_path / "test_cases.py"
    case_file.write_text(CASES, encoding="utf-8")
    # Before the hook: old pytest versions expand a raw 350,001-byte value into
    # the node ID. Newer versions may already compact it, so inspect collection
    # rather than require those versions to reproduce the old failure.
    collected = run_child(tmp_path, "--collect-only")
    assert collected.returncode == 0, collected.stdout[-4000:]
    oversized_before = any(len(line) > 32767 for line in collected.stdout.splitlines())
    if oversized_before:
        before = run_child(tmp_path)
        assert before.returncode == 1
        assert not (tmp_path / "observed.jsonl").exists()
        assert "error" in before.stdout.lower()
    (tmp_path / "conftest.py").write_text(HOOK_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    collected = run_child(tmp_path, "--collect-only")
    assert collected.returncode == 0, collected.stdout[-4000:]
    node_ids = [line for line in collected.stdout.splitlines() if line.startswith("test_cases.py::")]
    assert len(node_ids) == len(set(node_ids)) == 6
    assert max(map(len, node_ids)) < 1000
    after = run_child(tmp_path)
    assert after.returncode == 0, after.stdout[-4000:]
    assert "6 passed" in after.stdout
    observed = [json.loads(line) for line in (tmp_path / "observed.jsonl").read_text().splitlines()]
    assert [row["length"] for row in observed] == [350001, 350001]


@pytest.mark.parametrize("traceback_style", ["no", "short", "line"])
@pytest.mark.parametrize("ci_output", [False, True], ids=["local-output", "ci-output"])
def test_failing_assertions_are_not_hidden(tmp_path, monkeypatch, traceback_style, ci_output):
    # Local terminals can omit the exception message from the short summary.
    # Exercise both environments rather than depend on how CI formats stdout.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("BUILD_NUMBER", raising=False)
    monkeypatch.setenv("COLUMNS", "80")
    if ci_output:
        monkeypatch.setenv("CI", "true")
    (tmp_path / "conftest.py").write_text(HOOK_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "test_failure.py").write_text(
        "import pytest\n@pytest.mark.parametrize('data', [b'x' * 350001])\n"
        "def test_still_fails(data):\n    assert len(data) == 0\n", encoding="utf-8",
    )
    result = run_child(tmp_path, "--tb=" + traceback_style)
    assert result.returncode == pytest.ExitCode.TESTS_FAILED
    assert "1 failed" in result.stdout
    assert "len350001" in result.stdout
    assert "environment variable is longer" not in result.stdout
    # Console text is not evidence of exception type: --tb=no suppresses it,
    # and pytest may truncate the summary. Check the actual test-phase report.
    reports = json.loads((tmp_path / "pytest-outcomes.json").read_text(encoding="utf-8"))
    assert reports == [
        {"phase": "setup", "outcome": "passed", "exception_type": None},
        {"phase": "call", "outcome": "failed", "exception_type": "AssertionError"},
        {"phase": "teardown", "outcome": "passed", "exception_type": None},
    ]


def test_setup_errors_are_distinct_from_assertion_failures(tmp_path):
    (tmp_path / "test_setup_error.py").write_text(
        "import pytest\n@pytest.fixture\ndef broken():\n"
        "    raise RuntimeError('intentional setup error')\n"
        "def test_not_reached(broken):\n    assert False\n", encoding="utf-8",
    )
    result = run_child(tmp_path)
    assert result.returncode == pytest.ExitCode.TESTS_FAILED
    reports = json.loads((tmp_path / "pytest-outcomes.json").read_text(encoding="utf-8"))
    assert reports == [
        {"phase": "setup", "outcome": "failed", "exception_type": "RuntimeError"},
        {"phase": "teardown", "outcome": "passed", "exception_type": None},
    ]
