"""Offline store tests. Fixtures follow the existing web result/document contract."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from helix.freshness import cache_metadata, requires_live_evidence
from helix.knowledge import KnowledgeStore


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebDocument:
    title: str
    url: str
    text: str


URL = "https://example.com/streaming"
RESULT = SearchResult("Streaming", URL, "Streaming reduces latency.")
DOC = WebDocument("Streaming", URL, "Streaming reduces perceived latency.")


@pytest.fixture
def store(tmp_path):
    return KnowledgeStore(tmp_path / "knowledge.sqlite3")


def age_entry(store, delta, kind="page"):
    stamp = (datetime.now(timezone.utc) - delta).isoformat()
    with store.connect() as c:
        c.execute("UPDATE web_knowledge SET updated_at=?,source_type=?", (stamp, kind))
    return stamp


@pytest.mark.parametrize("query", [
    "latest streaming research", "streaming today", "current price",
    "weather tomorrow", "who is the CEO", "up-to-date streaming sources",
    "availability this week", "recent Python changes", "news yesterday",
])
def test_fresh_queries_never_consume_cache(store, query):
    store.learn(query, [RESULT], [DOC])
    assert requires_live_evidence(query)
    assert store.retrieve(query) == []
    assert store.list_entries()[0]["last_used_at"] is None


def test_new_page_provenance_and_metadata(store):
    assert store.learn("streaming latency", [RESULT], [DOC]) == 1
    hit = store.retrieve("streaming latency")[0]
    assert hit["url"] == URL
    assert hit["source_type"] == "page"
    assert hit["cache_status"] == "eligible"
    assert "perceived latency" in hit["content"]
    assert hit["expires_at"] > hit["updated_at"]


@pytest.mark.parametrize("kind,delta,expected", [
    ("page", timedelta(days=6), True),
    ("page", timedelta(days=8), False),
    ("snippet", timedelta(hours=23), True),
    ("snippet", timedelta(hours=25), False),
    ("web", timedelta(hours=25), False),
])
def test_age_limits_and_legacy_rows(store, kind, delta, expected):
    store.learn("streaming", [RESULT], [DOC])
    age_entry(store, delta, kind)
    assert bool(store.retrieve("streaming")) is expected
    assert store.count() == 1  # Expiry excludes; it does not erase saved history.


@pytest.mark.parametrize("stamp", ["", "not-a-date", "2026-09-18T10:00:00"])
def test_invalid_or_ambiguous_dates_are_excluded(store, stamp):
    store.learn("streaming", [RESULT], [DOC])
    with store.connect() as c:
        c.execute("UPDATE web_knowledge SET updated_at=?", (stamp,))
    assert store.retrieve("streaming") == []
    assert store.list_entries()[0]["cache_status"] == "invalid_timestamp"


def test_future_timestamp_is_excluded(store):
    store.learn("streaming", [RESULT], [DOC])
    age_entry(store, timedelta(days=-1))
    assert store.retrieve("streaming") == []
    assert store.list_entries()[0]["cache_status"] == "future_timestamp"


def test_reads_never_extend_retrieval_date(store):
    store.learn("streaming", [RESULT], [DOC])
    before = store.list_entries()[0]["updated_at"]
    store.retrieve("streaming")
    after = store.list_entries()[0]
    assert after["updated_at"] == before
    assert after["last_used_at"] is not None


def test_identical_research_does_not_launder_timestamp(store):
    store.learn("streaming", [RESULT], [DOC])
    original = age_entry(store, timedelta(days=8))
    assert store.learn("streaming again", [RESULT], [DOC]) == 0
    assert store.list_entries()[0]["updated_at"] == original
    assert store.retrieve("streaming") == []


def test_failed_page_fetch_cannot_downgrade_or_refresh_page(store):
    store.learn("streaming", [RESULT], [DOC])
    original = age_entry(store, timedelta(days=8))
    assert store.learn("streaming", [RESULT], []) == 0
    entry = store.list_entries()[0]
    assert entry["updated_at"] == original
    assert entry["source_type"] == "page"


def test_changed_page_updates_but_preserves_created_at(store):
    store.learn("streaming", [RESULT], [DOC])
    created = store.list_entries()[0]["created_at"]
    age_entry(store, timedelta(days=8))
    revised = WebDocument(DOC.title, URL, DOC.text + " Revised guidance.")
    assert store.learn("revised streaming", [RESULT], [revised]) == 1
    assert store.retrieve("streaming")[0]["content"] == revised.text
    assert store.list_entries()[0]["created_at"] == created
    assert store.count() == 1


def test_snippet_can_be_upgraded_to_page(store):
    store.learn("streaming", [RESULT], [])
    assert store.list_entries()[0]["source_type"] == "snippet"
    assert store.learn("streaming", [RESULT], [DOC]) == 1
    assert store.retrieve("streaming")[0]["source_type"] == "page"


def test_upsert_compatibility_for_changed_snippets(store):
    first = SearchResult("Title", URL, "old text")
    second = SearchResult("Title 2", URL, "new text")
    assert store.learn("first query", [first], []) == 1
    assert store.learn("second query", [second], []) == 1
    hit = store.retrieve("new text")[0]
    assert hit["title"] == "Title 2"
    assert hit["query"] == "second query"
    assert store.count() == 1


def test_empty_evidence_does_not_renew_cache(store):
    store.learn("streaming", [RESULT], [DOC])
    original = age_entry(store, timedelta(days=8))
    assert store.learn("streaming", [SearchResult("Streaming", URL, "")], []) == 0
    assert store.list_entries()[0]["updated_at"] == original


def test_zero_limit_and_clear(store):
    store.learn("streaming", [RESULT], [DOC])
    assert store.retrieve("streaming", limit=0) == []
    assert store.clear() == 1
    assert store.count() == 0


def test_expiry_boundary_and_timezone_equivalence():
    now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    assert cache_metadata("2026-09-11T12:00:00+00:00", "page", now)["cache_status"] == "expired"
    assert cache_metadata("2026-09-18T08:00:00-04:00", "page", now)["age_seconds"] == 0
