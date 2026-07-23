from onionlens.models import SearchResult, dedupe


def make(url, title="t"):
    return SearchResult(title=title, onion_url=url, description="", source="ahmia")


def test_address_normalizes_host():
    r = make("http://ExampleAbc.onion/path?q=1")
    assert r.address == "exampleabc.onion"


def test_dedupe_collapses_mirrors():
    results = [
        make("http://abc.onion/one", "first"),
        make("http://abc.onion/two", "mirror"),
        make("http://xyz.onion", "other"),
    ]
    unique = dedupe(results)
    assert len(unique) == 2
    assert unique[0].title == "first"
