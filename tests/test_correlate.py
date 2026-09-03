from onionlens.config import Config
from onionlens.correlate import correlate
from onionlens.models import SearchResult
from onionlens.pricing import CostMeter


def make(n):
    return [
        SearchResult(title=f"s{i}", onion_url=f"http://a{i}.onion", description="x", source="ahmia")
        for i in range(n)
    ]


def test_correlate_parses_json_and_meters(fake_client):
    cfg = Config(anthropic_api_key="x")
    meter = CostMeter()
    report = correlate(cfg, "q", make(3), client=fake_client, meter=meter)
    assert report["summary"] == "ok"
    assert any(item[0] == "correlation" for item in meter.items)


def test_correlate_caps_input(fake_client):
    cfg = Config(anthropic_api_key="x", max_correlate=5)
    # should not raise even with many results; cap applied internally
    report = correlate(cfg, "q", make(50), client=fake_client)
    assert "summary" in report


def test_correlate_empty_results():
    cfg = Config(anthropic_api_key="x")
    report = correlate(cfg, "q", [])
    assert report["summary"] == "No results to correlate."
    assert report["unrelated"] == []


def test_correlate_passes_through_unrelated():
    from conftest import FakeClient

    cfg = Config(anthropic_api_key="x")
    client = FakeClient('{"summary": "ok", "unrelated": ["a0.onion"]}')
    report = correlate(cfg, "q", make(2), client=client)
    assert report["unrelated"] == ["a0.onion"]
