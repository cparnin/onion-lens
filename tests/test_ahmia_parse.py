from onionlens.config import Config
from onionlens.search.ahmia import AhmiaSearch

SAMPLE_HTML = """
<ol>
  <li class="result">
    <h4><a href="/search/redirect?redirect_url=http%3A%2F%2Fexampleforum.onion%2F">Example Forum</a></h4>
    <cite>http://exampleforum.onion/</cite>
    <p>A discussion forum about security research.</p>
    <span class="lastSeen" datetime="2026-07-01">1 week ago</span>
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


def make_engine():
    return AhmiaSearch(Config(openai_api_key="test"))


def test_parses_result_fields():
    results = make_engine().parse(SAMPLE_HTML)
    assert len(results) == 1  # the abuse result is screened out
    r = results[0]
    assert r.title == "Example Forum"
    assert r.onion_url == "http://exampleforum.onion/"
    assert r.address == "exampleforum.onion"
    assert r.last_seen == "2026-07-01"


def test_empty_html_returns_nothing():
    assert make_engine().parse("<ol></ol>") == []


def test_parse_tokens_extracts_hidden_field():
    tokens = AhmiaSearch.parse_tokens(HOME_HTML)
    assert tokens == {"9f5712": "ef2dcd"}


def test_respects_limit():
    many = "<ol>" + SAMPLE_HTML * 5 + "</ol>"
    results = make_engine().parse(many, limit=2)
    assert len(results) == 2
