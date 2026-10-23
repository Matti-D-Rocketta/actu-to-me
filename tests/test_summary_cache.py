import json
from datetime import datetime, timedelta, timezone

from src.summary_cache import SummaryCache, cache_key, summarize_with_cache

ITEM = {"title": "T", "link": "https://ex.com/a", "content": "x" * 1000}
OK = {"title": "T", "available": True, "summary_ai": "résumé"}


class CountingSummarizer:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def __call__(self, model, api_key, item, section_scope=""):
        self.calls += 1
        return dict(self.result)


def test_second_call_hits_cache_and_survives_reload(tmp_path):
    path = tmp_path / "c.json"
    fn = CountingSummarizer(OK)
    cache = SummaryCache(path)
    assert summarize_with_cache(cache, fn, "m", "k", ITEM, "scope") == OK
    assert summarize_with_cache(cache, fn, "m", "k", ITEM, "scope") == OK
    assert fn.calls == 1 and cache.hits == 1
    cache.save()

    reloaded = SummaryCache(path)
    assert summarize_with_cache(reloaded, fn, "m", "k", ITEM, "scope") == OK
    assert fn.calls == 1


def test_key_changes_with_model_content_or_scope():
    base = cache_key("m", ITEM, "s")
    assert cache_key("m2", ITEM, "s") != base
    assert cache_key("m", {**ITEM, "content": "other"}, "s") != base
    assert cache_key("m", ITEM, "other scope") != base


def test_failures_are_not_cached(tmp_path):
    fn = CountingSummarizer({"available": False, "fallback_note": "quota"})
    cache = SummaryCache(tmp_path / "c.json")
    summarize_with_cache(cache, fn, "m", "k", ITEM)
    summarize_with_cache(cache, fn, "m", "k", ITEM)
    assert fn.calls == 2 and len(cache) == 0


def test_expired_and_corrupt_cache(tmp_path):
    path = tmp_path / "c.json"
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    path.write_text(json.dumps({"k1": {"cached_at": old, "result": OK}, "k2": {"bad": 1}}), encoding="utf-8")
    assert len(SummaryCache(path, ttl_days=30)) == 0

    path.write_text("{not json", encoding="utf-8")
    assert len(SummaryCache(path)) == 0  # unreadable cache is ignored, no crash


def test_no_cache_passthrough():
    fn = CountingSummarizer(OK)
    summarize_with_cache(None, fn, "m", "k", ITEM)
    summarize_with_cache(None, fn, "m", "k", ITEM)
    assert fn.calls == 2
