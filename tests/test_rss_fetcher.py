import requests

from src import rss_fetcher
from tests.conftest import FakeResponse, make_rss

GOOD = "https://good.example/feed"
DEAD = "https://dead.example/feed"
HTTP500 = "https://broken.example/feed"
GARBAGE = "https://garbage.example/feed"


def _patch_network(monkeypatch, routes):
    def fake_get(url, headers=None, timeout=None):
        assert timeout, "every feed request must have a timeout"
        r = routes[url]
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(rss_fetcher.requests, "get", fake_get)
    # no article download during tests
    monkeypatch.setattr(rss_fetcher, "extract_fulltext", lambda url: "full text of " + url)


def test_parses_feed_items(monkeypatch, since_dt):
    _patch_network(monkeypatch, {GOOD: FakeResponse(make_rss([
        {"title": "Electrolyzer order", "link": "https://good.example/a?utm_source=rss"},
        {"title": "Fuel cell truck", "link": "https://good.example/b"},
    ]))})
    items = rss_fetcher.fetch_section("Hydro", [GOOD], since_dt)
    assert [it["title"] for it in items] == ["Electrolyzer order", "Fuel cell truck"]
    first = items[0]
    assert first["link"] == "https://good.example/a"  # tracking query removed
    assert first["source"] == "Test Feed"
    assert first["section"] == "Hydro"
    assert first["content"].startswith("full text of")


def test_dead_feeds_do_not_kill_section(monkeypatch, since_dt):
    _patch_network(monkeypatch, {
        DEAD: requests.ConnectionError("unreachable"),
        HTTP500: FakeResponse(status_code=500),
        GARBAGE: FakeResponse(b"<html>not a feed"),
        GOOD: FakeResponse(make_rss([{"title": "Still here", "link": "https://good.example/c"}])),
    })
    errors = []
    items = rss_fetcher.fetch_section("Hydro", [DEAD, HTTP500, GARBAGE, GOOD], since_dt, errors=errors)
    assert [it["title"] for it in items] == ["Still here"]
    assert {e["feed"] for e in errors} == {DEAD, HTTP500, GARBAGE}


def test_filters_old_items_and_dedupes(monkeypatch, since_dt):
    _patch_network(monkeypatch, {GOOD: FakeResponse(make_rss([
        {"title": "Recent", "link": "https://good.example/r"},
        {"title": "Recent", "link": "https://good.example/r"},
        {"title": "Old", "link": "https://good.example/o", "date": "Mon, 01 Jan 2024 08:00:00 GMT"},
    ]))})
    items = rss_fetcher.fetch_section("Hydro", [GOOD], since_dt)
    assert [it["title"] for it in items] == ["Recent"]


def test_bad_entry_is_skipped(monkeypatch, since_dt):
    _patch_network(monkeypatch, {GOOD: FakeResponse(make_rss([
        {"title": "Boom", "link": "https://good.example/boom"},
        {"title": "Fine", "link": "https://good.example/fine"},
    ]))})

    def flaky_extract(url):
        if "boom" in url:
            raise RuntimeError("extraction crash")
        return "ok"
    monkeypatch.setattr(rss_fetcher, "extract_fulltext", flaky_extract)
    items = rss_fetcher.fetch_section("Hydro", [GOOD], since_dt)
    assert [it["title"] for it in items] == ["Fine"]
