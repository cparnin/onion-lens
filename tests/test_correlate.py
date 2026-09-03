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


def test_correlate_includes_intel_context(fake_client):
    from onionlens.intel.base import IntelRecord

    cfg = Config(anthropic_api_key="x")
    intel = {"hibp": [IntelRecord(source="hibp", title="BigID Leak: 153,000,000 accounts",
                                  summary="identity documents", date="2026-08-01")]}
    correlate(cfg, "q", make(2), intel=intel, client=fake_client)
    prompt = fake_client.messages.last_messages[0]["content"]
    assert "Context (clearnet sources" in prompt
    assert "Known breaches (HIBP)" in prompt
    assert "BigID Leak" in prompt


def test_correlate_omits_context_without_intel(fake_client):
    cfg = Config(anthropic_api_key="x")
    correlate(cfg, "q", make(2), client=fake_client)
    assert "Context" not in fake_client.messages.last_messages[0]["content"]
