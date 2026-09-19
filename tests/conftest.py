"""Keep generated test labels small without changing test inputs or coverage."""
from __future__ import annotations

import hashlib


def pytest_make_parametrize_id(val: object, argname: str) -> str | None:
    """Summarize long strings/bytes before pytest builds PYTEST_CURRENT_TEST.

    Windows cannot store a 350,001-byte fixture in an environment variable.
    Only the automatically generated label changes; pytest still passes the
    complete original value to the test. Explicit IDs and short values retain
    pytest's standard behavior. This hook also applies to parametrized fixtures.
    """
    if not isinstance(val, (str, bytes)) or len(val) <= 128:
        return None
    data = val.encode("utf-8", errors="surrogatepass") if isinstance(val, str) else val
    digest = hashlib.sha256(data).hexdigest()[:12]
    return f"{argname[:32]}-{type(val).__name__}-len{len(val)}-{digest}"
