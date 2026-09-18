from __future__ import annotations
import argparse
import os
import secrets
from pathlib import Path
import uvicorn
from .core import Settings
from .server import create_app


def main():
    parser = argparse.ArgumentParser(description="Helix local founder prototype — no cloud spend by default")
    parser.add_argument("--config", type=Path, default=Path("config/demo.json"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ledger", type=Path, default=Path(".helix/ledger.sqlite3"))
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    settings = Settings.from_file(args.config)
    key = os.environ.get("HELIX_API_KEY")
    if not key:
        key = secrets.token_urlsafe(32)
        print("Local access key (paste into the browser; do not publish):", key, flush=True)
    print(f"Open http://127.0.0.1:{args.port} — local-only prototype. No model weights included.", flush=True)
    uvicorn.run(create_app(settings, key, args.ledger), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
