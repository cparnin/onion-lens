from onionlens.config import Config
from onionlens.models import SearchResult
from onionlens.store import Store


class FakeEmbedder:
    """Deterministic local embedder: letter-frequency vectors, no network."""

    def embed(self, texts):
        for t in texts:
            t = t.lower()
            yield [float(t.count(c)) for c in "abcdefghijklmnop"]


def make_store(tmp_path, **cfg):
    config = Config(anthropic_api_key="x", db_path=str(tmp_path / "t.db"), **cfg)
    return Store(config, embedder=FakeEmbedder())


def make(n):
    return [
        SearchResult(title=f"site {i}", onion_url=f"http://addr{i}.onion", description="d", source="ahmia")
        for i in range(n)
    ]


def test_upsert_and_count(tmp_path):
    store = make_store(tmp_path)
    store.upsert(make(3))
    assert store.count() == 3


def test_prune_enforces_max_rows(tmp_path):
    store = make_store(tmp_path, max_rows=5)
    store.upsert(make(10))
    assert store.count() == 5  # capped, oldest pruned


def test_dedupe_via_upsert_conflict(tmp_path):
    store = make_store(tmp_path)
    store.upsert(make(2))
    store.upsert(make(2))  # same addresses again
    assert store.count() == 2  # no duplicates


def test_search_matches_keywords(tmp_path):
    store = make_store(tmp_path)
    store.upsert([
        SearchResult(title="bitcoin mixer", onion_url="http://a1.onion",
                     description="tumbling service", source="ahmia"),
        SearchResult(title="forum board", onion_url="http://a2.onion",
                     description="general discussion", source="ahmia"),
    ])
    hits = store.search("bitcoin")
    assert hits
    assert hits[0]["title"] == "bitcoin mixer"


def test_search_survives_fts_operators(tmp_path):
    store = make_store(tmp_path)
    store.upsert(make(2))
    # operator syntax and punctuation must not raise
    store.search('"unclosed AND (NOT *')
    store.search("!!!")


def test_search_falls_back_without_embedder(tmp_path):
    class BrokenEmbedder:
        def embed(self, texts):
            raise RuntimeError("model not downloaded")

    config = Config(anthropic_api_key="x", db_path=str(tmp_path / "t.db"))
    store = Store(config, embedder=BrokenEmbedder())
    store.upsert([
        SearchResult(title="bitcoin mixer", onion_url="http://a1.onion",
                     description="tumbling service", source="ahmia"),
    ])
    hits = store.search("bitcoin")  # keyword-only fallback still works
    assert hits and hits[0]["title"] == "bitcoin mixer"


def test_backfill_replaces_incompatible_vectors(tmp_path):
    store = make_store(tmp_path)
    store.upsert(make(2))
    # simulate old OpenAI-era vectors with the wrong dimension
    store.conn.execute("UPDATE results SET embedding = ?", (b"\x00" * 24,))
    store.conn.commit()
    store.search("site")
    blobs = [row[0] for row in store.conn.execute("SELECT embedding FROM results")]
    assert all(b is not None and len(b) == 16 * 4 for b in blobs)


def test_migrates_fts_only_schema(tmp_path):
    import sqlite3

    db = str(tmp_path / "t.db")
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE results (
            address TEXT PRIMARY KEY, title TEXT, onion_url TEXT,
            description TEXT, source TEXT, last_seen TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO results VALUES (?, ?, ?, ?, ?, ?)",
        ("old.onion", "legacy row", "http://old.onion", "kept", "ahmia", "2026-01-01"),
    )
    conn.commit()
    conn.close()

    config = Config(anthropic_api_key="x", db_path=db)
    store = Store(config, embedder=FakeEmbedder())
    assert store.count() == 1
    assert store.search("legacy")[0]["title"] == "legacy row"
