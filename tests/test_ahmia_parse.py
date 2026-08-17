from onionlens.config import Config
from onionlens.search.ahmia import AhmiaSearch

# Mirrors Ahmia's real markup: date is in data-timestamp, visible text is relative.
SAMPLE_HTML = """
<ol>
  <li class="result">
    <h4><a href="/search/redirect?redirect_url=http%3A%2F%2Fexampleforum.onion%2F">Example Forum</a></h4>
    <cite>http://exampleforum.onion/</cite>
    <p>A discussion forum about security research.</p>
    <span class="lastSeen" data-timestamp="July 1, 2026, 1:00 p.m.">1 week</span>
  </li>
  <li class="result">
    <h4><a href="/search/redirect?redirect_url=http%3A%2F%2Fchildabuse.onion%2F">blocked title underage</a></h4>
    <cite>http://childabuse.onion/</cite>
    <p>should be dropped by the safety screen</p>
  </li>
</ol>
"""

HOME_HTML = """
<form id="searchForm" action="/search/" method="get">
  <input id="id_q" type="search" name="q">
  <input type="hidden" name="9f5712" value="ef2dcd">
  <input type="submit" value="Search">
</form>
"""

# No li.result wrapper: exercises the fallback path.
FALLBACK_HTML = """
<div>
  <a href="/search/redirect?redirect_url=http%3A%2F%2Ffallbacksite.onion%2F">Fallback Site</a>
  <a href="/search/redirect?redirect_url=http%3A%2F%2Fchildabuse.onion%2F">underage blocked</a>
</div>
"""


def make_engine():
    return AhmiaSearch(Config(anthropic_api_key="test"))


def test_parses_result_fields_including_last_seen():
    engine = make_engine()
    results = engine.parse(SAMPLE_HTML)
    assert len(results) == 1  # the abuse result is screened out
    r = results[0]
    assert r.title == "Example Forum"
    assert r.address == "exampleforum.onion"
    assert r.last_seen == "1 week"  # was blank before the data-timestamp fix
    assert engine.degraded is False


def test_empty_html_returns_nothing():
    assert make_engine().parse("<ol></ol>") == []


def test_parse_tokens_extracts_hidden_field():
    assert AhmiaSearch.parse_tokens(HOME_HTML) == {"9f5712": "ef2dcd"}


def test_respects_limit():
    many = "<ol>" + SAMPLE_HTML * 5 + "</ol>"
    assert len(make_engine().parse(many, limit=2)) == 2


def test_fallback_path_extracts_and_flags_degraded():
    engine = make_engine()
    results = engine.parse(FALLBACK_HTML)
    assert len(results) == 1  # abuse anchor screened out
    assert results[0].address == "fallbacksite.onion"
    assert engine.degraded is True  # signals markup likely changed
