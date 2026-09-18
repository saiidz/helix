"""Conservative cache admission; retrieval age is not a factual-accuracy guarantee."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# Explicit freshness requests and common volatile subjects never use old research
# as answer context. This heuristic is deliberately not a claim to detect every
# changing fact. It grants no network permission: Web Off remains Off.
_LIVE = re.compile(
    r"\b(latest|current|currently|today|tonight|tomorrow|yesterday|now|"
    r"recent|recently|up[- ]to[- ]date|as of|this (?:week|month|year)|"
    r"news|weather|forecast|prices?|pricing|exchange rates?|stock|stocks|"
    r"elections?|polls?|standings|availability|opening hours|"
    r"president|prime minister|ceo|officeholder|office-holder)\b",
    re.IGNORECASE,
)
PAGE_MAX_AGE = timedelta(days=7)
SNIPPET_MAX_AGE = timedelta(days=1)


def requires_live_evidence(query: str) -> bool:
    """True means exclude cached answer context, not permission to browse."""
    return bool(_LIVE.search(query))


def parse_retrieved_at(value: str) -> datetime | None:
    """Fail closed for missing, malformed, or timezone-ambiguous timestamps."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def cache_metadata(value: str, source_type: str, now: datetime | None = None) -> dict:
    """Describe eligibility, not whether the contents are true or up to date."""
    now = now or datetime.now(timezone.utc)
    retrieved = parse_retrieved_at(value)
    # Legacy 'web' rows may be snippets, so use the shorter retention window.
    max_age = PAGE_MAX_AGE if source_type == "page" else SNIPPET_MAX_AGE
    if retrieved is None:
        return {"cache_status": "invalid_timestamp", "age_seconds": None,
                "expires_at": None}
    age = (now - retrieved).total_seconds()
    status = "eligible" if 0 <= age < max_age.total_seconds() else "expired"
    if age < 0:
        status = "future_timestamp"
    return {"cache_status": status, "age_seconds": age,
            "expires_at": (retrieved + max_age).isoformat()}
