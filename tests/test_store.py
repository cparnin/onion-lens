from onionlens.config import Config
from onionlens.models import SearchResult
from onionlens.pricing import CostMeter
from onionlens.store import Store


def make(n):
    return [
        SearchResult(title=f"site {i}", onion_url=f"http://addr{i}.onion", description="d", source="ahmia")
        for i in range(n)
    ]


def test_upsert_and_count(tmp_path, fake_client):
    cfg = Config(openai_api_key="x", db_path=str(tmp_path / "t.db"))
    store = Store(cfg, client=fake_client)
    store.upsert(make(3))
    assert store.count() == 3


def test_prune_enforces_max_rows(tmp_path, fake_client):
    cfg = Config(openai_api_key="x", db_path=str(tmp_path / "t.db"), max_rows=5)
    store = Store(cfg, client=fake_client)
    store.upsert(make(10))
    assert store.count() == 5  # capped, oldest pruned


def test_meter_records_embedding_cost(tmp_path, fake_client):
    cfg = Config(openai_api_key="x", db_path=str(tmp_path / "t.db"))
    store = Store(cfg, client=fake_client)
    meter = CostMeter()
    store.upsert(make(2), meter)
    assert len(meter.items) == 1
    assert meter.items[0][0] == "embeddings"


def test_dedupe_via_upsert_conflict(tmp_path, fake_client):
    cfg = Config(openai_api_key="x", db_path=str(tmp_path / "t.db"))
    store = Store(cfg, client=fake_client)
    store.upsert(make(2))
    store.upsert(make(2))  # same addresses again
    assert store.count() == 2  # no duplicates
