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


def make_engine():
    cfg = Config(openai_api_key="test")
    return AhmiaSearch(cfg)


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
