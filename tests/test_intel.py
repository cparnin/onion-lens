"""Intel sources: term matching, per-source parsing, caching, and gathering.
All tests use fixtures and monkeypatched fetches; no network."""

import json
import time

from onionlens.config import Config
from onionlens.intel import gather_intel
from onionlens.intel.base import (
    IntelRecord,
    cached_get_text,
    match_score,
    query_terms,
    strip_tags,
)
from onionlens.intel.hibp import HibpBreaches
from onionlens.intel.news import BreachNews, parse_rss
from onionlens.intel.ransomwatch import Ransomwatch


def cfg(tmp_path, **kw):
    return Config(anthropic_api_key="x", db_path=str(tmp_path / "t.db"), **kw)


# --- helpers ---

def test_query_terms_adds_singulars_and_drops_short():
    terms = query_terms("driver's licenses on TV")
    assert "driver" in terms and "licenses" in terms and "license" in terms
    assert "s" not in terms and "on" not in terms and "tv" not in terms


def test_match_score_counts_terms():
    terms = query_terms("driver licenses")
    assert match_score(terms, "Fake Driver's License shop") >= 2
    assert match_score(terms, "cooking recipes") == 0


def test_strip_tags():
    assert strip_tags("<p>Hello <b>world</b></p>") == "Hello world"


def test_record_key_stable_without_url():
    a = IntelRecord(source="x", title="t", summary="s")
    b = IntelRecord(source="x", title="t", summary="different")
    assert a.key == b.key
    assert IntelRecord(source="x", title="t", summary="s", url="http://u").key == "http://u"


# --- caching ---

def test_cached_get_text_caches_and_serves_stale_on_failure(tmp_path, monkeypatch):
    config = cfg(tmp_path)
    calls = []

    class Resp:
        text = "payload"
        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        calls.append(url)
        return Resp()

    monkeypatch.setattr("onionlens.intel.base.requests.get", fake_get)
    assert cached_get_text(config, "http://x", "c.txt", ttl=3600) == "payload"
    assert cached_get_text(config, "http://x", "c.txt", ttl=3600) == "payload"
    assert len(calls) == 1  # second read served from cache

    # expire the cache, then fail the fetch: stale cache is served
    def boom(url, **kw):
        raise RuntimeError("down")

    monkeypatch.setattr("onionlens.intel.base.requests.get", boom)
    monkeypatch.setattr(time, "time", lambda: time.mktime(time.localtime()) + 10**6)
    assert cached_get_text(config, "http://x", "c.txt", ttl=1) == "payload"


# --- sources ---

HIBP_FIXTURE = [
    {
        "Name": "BigID", "Title": "BigID Leak", "BreachDate": "2026-08-01",
        "PwnCount": 153000000,
        "Description": "<p>A dump of North American identity documents.</p>",
        "DataClasses": ["Driver's licenses", "Names"],
    },
    {
        "Name": "PetForum", "Title": "Pet Forum", "BreachDate": "2020-01-01",
        "PwnCount": 100, "Description": "Pet lovers forum.",
        "DataClasses": ["Email addresses"],
    },
]


def test_hibp_filters_and_formats(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "onionlens.intel.hibp.cached_get_json", lambda *a, **k: HIBP_FIXTURE
    )
    hits = HibpBreaches(cfg(tmp_path)).search("driver's licenses")
    assert len(hits) == 1
    assert hits[0].title == "BigID Leak: 153,000,000 accounts"
    assert "Driver's licenses" in hits[0].summary
    assert hits[0].url.endswith("/breach/BigID")


RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
<item><title>153M driver's licenses leaked on forum</title>
<link>http://example.com/a</link>
<description><![CDATA[<p>An ID verification provider is suspected.</p>]]></description>
<pubDate>Mon, 01 Sep 2026 00:00:00 GMT</pubDate></item>
<item><title>New ransomware group emerges</title>
<link>http://example.com/b</link>
<description>Unrelated story.</description>
<pubDate>Tue, 02 Sep 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_parse_rss_extracts_items():
    items = parse_rss(RSS_FIXTURE)
    assert len(items) == 2
    assert items[0]["title"].startswith("153M")
    assert "<p>" not in items[0]["description"]
    assert parse_rss("not xml") == []


def test_news_filters_by_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "onionlens.intel.news.cached_get_text", lambda *a, **k: RSS_FIXTURE
    )
    hits = BreachNews(cfg(tmp_path)).search("driver licenses")
    assert len(hits) == 1
    assert hits[0].url == "http://example.com/a"


RW_FIXTURE = [
    {"post_title": "DMV Data Services Inc", "group_name": "lockdata",
     "discovered": "2026-08-15 10:00:00.000000"},
    {"post_title": "Bakery Co", "group_name": "crumble",
     "discovered": "2026-08-16 10:00:00.000000"},
]


def test_ransomwatch_filters_by_title(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "onionlens.intel.ransomwatch.cached_get_json", lambda *a, **k: RW_FIXTURE
    )
    hits = Ransomwatch(cfg(tmp_path)).search("DMV data")
    assert len(hits) == 1
    assert hits[0].date == "2026-08-15"
    assert "lockdata" in hits[0].summary


# --- gathering ---

def test_gather_intel_isolates_failures_and_screens(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "onionlens.intel.hibp.cached_get_json", lambda *a, **k: HIBP_FIXTURE
    )
    monkeypatch.setattr(
        "onionlens.intel.news.cached_get_text",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("feed down")),
    )
    monkeypatch.setattr(
        "onionlens.intel.ransomwatch.cached_get_json", lambda *a, **k: []
    )
    records, errors = gather_intel(cfg(tmp_path), "driver's licenses")
    assert "hibp" in records and len(records["hibp"]) == 1
    assert "ransomwatch" not in records  # empty, omitted
    assert errors == {}  # news failure is per-feed, swallowed inside the source
