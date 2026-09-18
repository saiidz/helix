"""Run dependency-free browser-module tests when Node is available.

Node is only a development-test dependency, not a HELIX runtime dependency.
The Windows gate reports a skip rather than pretending the checks ran without it.
"""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_engineer_workbench_primitives():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is not installed; run the Engineer checks on a Node-enabled development machine")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, "--test", "tests/engineer_workbench.test.mjs"],
        cwd=root, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
