"""Explicit, read-only check of this checkout's web connector; no model call."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_web(query: str, research: Callable | None = None) -> tuple[dict, int]:
    """Return a diagnostic and exit code; injected research is for fixture tests."""
    query = " ".join(query.split())
    report = {
        "checked_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "scope": "web connector in this checkout, not the running UI or model",
        "status": "unavailable",
        "search_results": 0,
        "readable_pages": 0,
        "sources": [],
    }
    if not query or len(query) > 500:
        report["error"] = "Supply a public search query between 1 and 500 characters."
        return report, 2
    try:
        if research is None:
            from helix.web import research_web
            research = research_web
        results, documents = research(query, search_limit=3, fetch_limit=2)
        report["search_results"] = len(results)
        report["readable_pages"] = sum(bool(doc.text.strip()) for doc in documents)
        report["sources"] = [{"title": item.title, "url": item.url} for item in results[:3]]
    except Exception as exc:
        # Do not dump query text, local configuration, credentials, or network
        # exception details into a diagnostic that may be shared publicly.
        report["error"] = f"Connector check failed ({type(exc).__name__}). Check dependencies and network access."
        return report, 1
    if report["search_results"] and report["readable_pages"]:
        report["status"] = "ok"
        return report, 0
    if report["search_results"]:
        report["status"] = "partial"
        report["error"] = "Search returned results, but no readable page was fetched."
    else:
        report["error"] = "No usable search results; live connectivity is not confirmed."
    return report, 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="Python official documentation",
                        help="Public search text. Do not include private data or credentials.")
    args = parser.parse_args()
    report, code = check_web(args.query)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
