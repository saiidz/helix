from helix.knowledge import KnowledgeStore
from helix.web import SearchResult, WebDocument


def test_knowledge_learns_and_retrieves_with_provenance(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    results = [
        SearchResult(
            title="Helix streaming notes",
            url="https://example.com/streaming",
            snippet="Streaming reduces perceived latency.",
        )
    ]
    documents = [
        WebDocument(
            title="Helix streaming notes",
            url="https://example.com/streaming",
            text="Streaming responses reduce perceived latency by showing output as it arrives.",
        )
    ]

    learned = store.learn("how to make responses faster", results, documents)
    assert learned == 1
    assert store.count() == 1

    hits = store.retrieve("streaming latency")
    assert len(hits) == 1
    assert hits[0]["url"] == "https://example.com/streaming"
    assert "perceived latency" in hits[0]["content"]


def test_knowledge_upserts_same_source(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")

    first = [SearchResult("Title","https://example.com/a","old text")]
    second = [SearchResult("Title 2","https://example.com/a","new text")]

    assert store.learn("first query", first, []) == 1
    assert store.learn("second query", second, []) == 1
    assert store.count() == 1

    hits = store.retrieve("new text")
    assert hits[0]["title"] == "Title 2"
    assert hits[0]["query"] == "second query"
