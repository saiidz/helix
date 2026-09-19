"""Read-only local startup diagnostics. No inference, credentials, or remote probes."""
from __future__ import annotations

import argparse
import http.client
import importlib
import ipaddress
import json
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 131072
ROLES = {"companion", "engineer", "sage"}
REQUIRED_FILES = (
    "helix/__main__.py", "helix/core.py", "helix/server.py",
    "helix/engineer_api.py", "helix/learning_api.py",
    "helix/static/index.html", "helix/static/agent.html", "helix/static/learning.html",
    "START_HELIX.cmd", "START_HELIX_AGENT.cmd", "requirements-dev.txt",
)


class StartupError(Exception):
    """An operator-readable error that must not embed private configuration."""


@dataclass(frozen=True)
class Endpoint:
    role: str
    host: str
    port: int
    path: str
    model_id: str


def read_config(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise StartupError("Configuration is too large; review it locally.")
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise StartupError("Cannot read valid UTF-8 JSON configuration. Check config/local.json locally; do not share its contents.") from exc
    if not isinstance(data, dict):
        raise StartupError("Configuration must be a JSON object.")
    return data


def local_endpoints(data: dict) -> list[Endpoint]:
    profiles = data.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 3:
        raise StartupError("Configure exactly one local profile for Companion, Engineer and Sage.")
    endpoints = []
    seen = set()
    for profile in profiles:
        if not isinstance(profile, dict):
            raise StartupError("Invalid model profile.")
        role = profile.get("role")
        if not isinstance(role, str) or role not in ROLES or role in seen:
            raise StartupError("Configure exactly one local profile for each HELIX role.")
        seen.add(role)
        if profile.get("kind") != "local":
            raise StartupError("This local-readiness check accepts local profiles only; it will not probe cloud or demo providers.")
        model = profile.get("model_id")
        if not isinstance(model, str) or not model.strip() or len(model) > 128:
            raise StartupError(f"Set the installed model ID for {role}.")
        if model.startswith("REPLACE_") or any(ord(c) < 32 for c in model):
            raise StartupError(f"Replace the placeholder model ID for {role}.")
        base = profile.get("base_url")
        if not isinstance(base, str) or any(ord(c) < 33 for c in base):
            raise StartupError(f"Invalid local endpoint for {role}.")
        try:
            parsed = urlsplit(base)
            address = ipaddress.ip_address(parsed.hostname or "")
            port = parsed.port if parsed.port is not None else 80
            valid = (parsed.scheme == "http" and address.is_loopback
                     and not parsed.username and not parsed.password
                     and not parsed.query and not parsed.fragment
                     and 1 <= port <= 65535)
        except ValueError:
            valid = False
        if not valid:
            raise StartupError(f"Endpoint for {role} must be HTTP on a literal loopback IP, without credentials, query or fragment.")
        endpoints.append(Endpoint(role, str(address), port, parsed.path.rstrip("/") + "/models", model))
    return endpoints


def fetch_model_ids(endpoint: Endpoint) -> set[str]:
    """HTTPConnection uses no proxy environment or redirect handler; only literal loopback."""
    try:
        if not ipaddress.ip_address(endpoint.host).is_loopback or not 1 <= endpoint.port <= 65535:
            raise ValueError("Non-local endpoint")
        if not endpoint.path.startswith("/") or any(ord(c) < 33 for c in endpoint.path):
            raise ValueError("Invalid request path")
    except (ValueError, TypeError) as exc:
        raise StartupError("Diagnostic probes are restricted to literal loopback endpoints.") from exc
    connection = http.client.HTTPConnection(endpoint.host, endpoint.port, timeout=3)
    try:
        connection.request("GET", endpoint.path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise StartupError(f"Local model-list request failed for {endpoint.role}; redirects and non-200 responses are not accepted.")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise StartupError("Local model-list response exceeded the diagnostic size limit.")
        data = json.loads(body)
        models = data.get("data") if isinstance(data, dict) else None
        if not isinstance(models, list) or not models:
            raise StartupError("The local server returned no usable model list.")
        if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] for item in models):
            raise StartupError("The local server returned an invalid model list.")
        return {item["id"] for item in models}
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise StartupError(f"Cannot read the local model list for {endpoint.role}. Start its configured model server and retry.") from exc
    finally:
        connection.close()


def check_models(endpoints: list[Endpoint]) -> None:
    cache: dict[tuple, set[str]] = {}
    for endpoint in endpoints:
        key = (endpoint.host, endpoint.port, endpoint.path)
        if key not in cache:
            cache[key] = fetch_model_ids(endpoint)
        if endpoint.model_id not in cache[key]:
            raise StartupError(f"Configured model ID for {endpoint.role} is not advertised by its local server. Compare config/local.json with that server's /models response locally.")


def check_port(port: int) -> None:
    if not 1024 <= port <= 65535:
        raise StartupError("HELIX app port must be between 1024 and 65535.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise StartupError("HELIX app port is unavailable. Stop only the old HELIX app terminal with Ctrl+C; leave the model server running. No process was killed.") from exc


def check_tracked_private(root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", ".helix", ".venv", "config/local.json",
             "*.gguf", "*.safetensors", "*.onnx"],
            cwd=root, capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StartupError("Cannot check Git's private-file tracking; no files were changed.") from exc
    if result.returncode:
        raise StartupError("Cannot check Git's private-file tracking in this checkout.")
    if result.stdout:
        raise StartupError("Private runtime files, local config or model weights are tracked by Git. Review locally before proceeding; nothing was removed.")


def check_imports_and_schema(data: dict) -> None:
    try:
        core = importlib.import_module("helix.core")
        core.Settings.model_validate(data)
        importlib.import_module("helix.__main__")
    except Exception as exc:
        raise StartupError("Application imports or configuration validation failed. Run SETUP_WINDOWS.cmd to check dependencies, then review the configuration locally. No configuration values are printed by this check.") from exc


def run_checks(root: Path, config: Path, *, offline: bool, port: int, tracked_private: bool = False) -> int:
    stage = "Python"
    try:
        if sys.version_info[:2] != (3, 13):
            raise StartupError("These Windows launchers require Python 3.13 in .venv. Run SETUP_WINDOWS.cmd.")
        print("PASS: Python 3.13", flush=True)
        stage = "checkout files"
        if any(not (root / name).is_file() for name in REQUIRED_FILES):
            raise StartupError("The checkout is incomplete or outdated. Fetch and fast-forward feat/codex-inspired-ui-v02 without discarding local changes.")
        print("PASS: required app and launcher files", flush=True)
        if tracked_private:
            stage = "private files in Git"
            check_tracked_private(root)
            print("PASS: private runtime paths and model-weight patterns are not tracked", flush=True)
        stage = "configuration"
        data = read_config(config)
        endpoints = local_endpoints(data)
        check_imports_and_schema(data)
        print("PASS: local configuration and launcher imports", flush=True)
        if offline:
            print("OFFLINE checks passed. Model availability and app port were NOT checked. This is not a deployment or full-test pass.", flush=True)
            return 0
        stage = "app port"
        check_port(port)
        print("PASS: app port currently available", flush=True)
        stage = "local model list"
        check_models(endpoints)
        print("PASS: all configured local model IDs are advertised. No generation or model-quality check was performed.", flush=True)
        return 0
    except StartupError as exc:
        print(f"FAIL [{stage}]: {exc}", flush=True)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Skip ALL model probes and the app port check")
    parser.add_argument("--tracked-private", action="store_true", help="Also refuse private runtime files tracked by Git")
    parser.add_argument("--config", type=Path, default=ROOT / "config/local.json")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return run_checks(ROOT, args.config, offline=args.offline, port=args.port, tracked_private=args.tracked_private)


if __name__ == "__main__":
    raise SystemExit(main())
