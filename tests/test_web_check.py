from types import SimpleNamespace

import pytest

from tools.check_web import check_web


RESULT = SimpleNamespace(title="Fixture page", url="https://example.com/page")
DOC = SimpleNamespace(text="Fixture text, not live web evidence.")


def test_success_requires_search_and_readable_page():
    calls = []
    def research(query, **kwargs):
        calls.append((query, kwargs))
        return [RESULT], [DOC]
    report, code = check_web(" public   information ", research)
    assert code == 0 and report["status"] == "ok"
    assert report["search_results"] == report["readable_pages"] == 1
    assert calls == [("public information", {"search_limit": 3, "fetch_limit": 2})]
    assert "not the running UI or model" in report["scope"]
    assert "query" not in report


@pytest.mark.parametrize("documents", [[], [SimpleNamespace(text="  ")]])
def test_snippets_only_are_partial(documents):
    report, code = check_web("public info", lambda *a, **k: ([RESULT], documents))
    assert code != 0 and report["status"] == "partial"


def test_empty_results_do_not_claim_connectivity():
    report, code = check_web("public info", lambda *a, **k: ([], []))
    assert code != 0 and report["status"] == "unavailable"


def test_failures_do_not_leak_exception_details():
    def fail(*args, **kwargs):
        raise RuntimeError("private-token-do-not-share")
    report, code = check_web("public info", fail)
    assert code == 1 and report["status"] == "unavailable"
    assert "RuntimeError" in report["error"]
    assert "private-token" not in str(report)


@pytest.mark.parametrize("query", ["", "   ", "x" * 501])
def test_invalid_query_does_not_make_network_call(query):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid query must not initiate research")
    report, code = check_web(query, unexpected)
    assert code == 2
    assert report["search_results"] == 0
