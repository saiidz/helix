import socket

import pytest

from helix import web


def test_private_urls_are_blocked():
    with pytest.raises(web.WebError):
        web.validate_public_url("http://127.0.0.1/private")

    with pytest.raises(web.WebError):
        web.validate_public_url("http://169.254.169.254/latest/meta-data")


def test_standard_ports_only(monkeypatch):
    monkeypatch.setattr(web, "_public_host", lambda hostname: True)

    assert web.validate_public_url("https://example.com/path") == "https://example.com/path"

    with pytest.raises(web.WebError):
        web.validate_public_url("https://example.com:8443/path")


def test_duckduckgo_redirect_normalization():
    value = (
        "https://duckduckgo.com/l/?uddg="
        "https%3A%2F%2Fexample.com%2Farticle%3Fx%3D1"
    )
    assert web._normalize_ddg_url(value) == "https://example.com/article?x=1"


def test_search_parser_extracts_results():
    parser = web._SearchParser()
    parser.feed(
        '<a class="result__a" href="https://example.com/a">Example title</a>'
        '<a class="result__snippet">Useful snippet text</a>'
    )
    assert len(parser.results) == 1
    assert parser.results[0].title == "Example title"
    assert parser.results[0].url == "https://example.com/a"
    assert parser.results[0].snippet == "Useful snippet text"
