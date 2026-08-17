"""Persistent knowledge base.

Stores every result in a local SQLite file so past sightings can be searched
across sessions, not just within one query. Search is hybrid and fully local:

- FTS5 full-text index with BM25 ranking for exact keyword matches.
- Local embeddings (fastembed, ONNX, no PyTorch) for fuzzy semantic matches,
  so "hitman" can find a row described as "contract killer". The model is
  downloaded once on first use and cached; embedding costs nothing per run.

The two rankings are merged with reciprocal rank fusion. If the embedding
model is unavailable (for example, offline before the first download), search
degrades to keyword-only instead of failing.

Size is bounded: the table is capped at config.max_rows and the oldest rows are
pruned on each write, so the database cannot grow without limit.
"""

import re
import sqlite3
import struct

import numpy as np

from .config import Config
from .models import SearchResult


def _pack(vec) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes) -> np.ndarray:
    count = len(blob) // 4
    return np.array(struct.unpack(f"{count}f", blob), dtype=np.float32)


class Store:
    def __init__(self, config: Config, embedder=None):
        self.cfg = config
        self._embedder = embedder  # injectable for testing
        self.conn = sqlite3.connect(config.db_path)
        self._init_db()

    @property
    def embedder(self):
        if self._embedder is None:
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding()  # default: bge-small-en-v1.5, 384 dims
        return self._embedder

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                address TEXT PRIMARY KEY,
                title TEXT,
                onion_url TEXT,
                description TEXT,
                source TEXT,
                last_seen TEXT,
                embedding BLOB
            )
            """
        )
        # Databases from the FTS5-only era lack the embedding column. Old
        # OpenAI-era databases have it but with incompatible vectors; those are
        # detected by dimension and re-embedded lazily in _backfill.
        cols = [row[1] for row in self.conn.execute("PRAGMA table_info(results)")]
        if "embedding" not in cols:
            self.conn.execute("ALTER TABLE results ADD COLUMN embedding BLOB")

        fts_exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='results_fts'"
        ).fetchone()
        self.conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS results_fts USING fts5(
                title, description, content='results', content_rowid='rowid'
            );
            CREATE TRIGGER IF NOT EXISTS results_fts_ai AFTER INSERT ON results BEGIN
                INSERT INTO results_fts(rowid, title, description)
                VALUES (new.rowid, new.title, new.description);
            END;
            CREATE TRIGGER IF NOT EXISTS results_fts_ad AFTER DELETE ON results BEGIN
                INSERT INTO results_fts(results_fts, rowid, title, description)
                VALUES ('delete', old.rowid, old.title, old.description);
            END;
            CREATE TRIGGER IF NOT EXISTS results_fts_au AFTER UPDATE ON results BEGIN
                INSERT INTO results_fts(results_fts, rowid, title, description)
                VALUES ('delete', old.rowid, old.title, old.description);
                INSERT INTO results_fts(rowid, title, description)
                VALUES (new.rowid, new.title, new.description);
            END;
            """
        )
        if not fts_exists:
            self.conn.execute("INSERT INTO results_fts(results_fts) VALUES('rebuild')")
        self.conn.commit()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, vec)) for vec in self.embedder.embed(texts)]

    def upsert(self, results: list[SearchResult]) -> int:
        if not results:
            return 0
        texts = [f"{r.title}. {r.description}" for r in results]
        try:
            vectors = self._embed(texts)
        except Exception:  # embedding model unavailable; store without vectors
            vectors = [None] * len(results)
        for result, vec in zip(results, vectors):
            self.conn.execute(
                """
                INSERT INTO results (address, title, onion_url, description, source, last_seen, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    last_seen=excluded.last_seen,
                    embedding=excluded.embedding
                """,
                (
                    result.address,
                    result.title,
                    result.onion_url,
                    result.description,
                    result.source,
                    result.last_seen,
                    _pack(vec) if vec is not None else None,
                ),
            )
        self.conn.commit()
        self._prune()
        return len(results)

    def _prune(self) -> int:
        """Keep only the newest max_rows rows. Returns number deleted."""
        cur = self.conn.execute(
            """
            DELETE FROM results
            WHERE rowid NOT IN (
                SELECT rowid FROM results ORDER BY rowid DESC LIMIT ?
            )
            """,
            (self.cfg.max_rows,),
        )
        self.conn.commit()
        return cur.rowcount

    def _backfill(self, dim: int) -> None:
        """Embed rows whose vector is missing or from an incompatible model."""
        rows = self.conn.execute(
            "SELECT address, title, description, embedding FROM results"
        ).fetchall()
        stale = [r for r in rows if r[3] is None or len(r[3]) != dim * 4]
        if not stale:
            return
        vectors = self._embed([f"{r[1]}. {r[2]}" for r in stale])
        for row, vec in zip(stale, vectors):
            self.conn.execute(
                "UPDATE results SET embedding = ? WHERE address = ?",
                (_pack(vec), row[0]),
            )
        self.conn.commit()

    def _keyword_ranked(self, query: str, k: int) -> list[str]:
        """Addresses of the best BM25 matches, best first.

        The raw query is reduced to bare terms before matching so FTS5 operator
        syntax in user input cannot break or subvert the query.
        """
        terms = re.findall(r"[A-Za-z0-9]+", query)
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        rows = self.conn.execute(
            """
            SELECT r.address
            FROM results_fts
            JOIN results r ON r.rowid = results_fts.rowid
            WHERE results_fts MATCH ?
            ORDER BY bm25(results_fts)
            LIMIT ?
            """,
            (match, k),
        ).fetchall()
        return [row[0] for row in rows]

    def _semantic_ranked(self, query: str, k: int) -> list[str]:
        """Addresses of the nearest embeddings by cosine, best first."""
        query_vec = np.array(self._embed([query])[0], dtype=np.float32)
        self._backfill(len(query_vec))
        query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-9)
        scored = []
        for address, blob in self.conn.execute(
            "SELECT address, embedding FROM results WHERE embedding IS NOT NULL"
        ):
            vec = _unpack(blob)
            vec = vec / (np.linalg.norm(vec) + 1e-9)
            scored.append((float(np.dot(query_vec, vec)), address))
        scored.sort(reverse=True)
        return [address for _, address in scored[:k]]

    def search(self, query: str, k: int = 10) -> list[dict]:
        """Hybrid keyword + semantic search, merged with reciprocal rank fusion."""
        pool = max(k * 3, 30)
        keyword = self._keyword_ranked(query, pool)
        try:
            semantic = self._semantic_ranked(query, pool)
        except Exception:  # embedding model unavailable; keyword-only
            semantic = []

        fused: dict[str, float] = {}
        for ranking in (keyword, semantic):
            for rank, address in enumerate(ranking):
                fused[address] = fused.get(address, 0.0) + 1.0 / (60 + rank)
        top = sorted(fused, key=fused.get, reverse=True)[:k]
        if not top:
            return []

        # placeholders is only "?,?,..." (one per address); the addresses
        # themselves are bound parameters, so this is not SQL injection.
        cols = "address, title, onion_url, description, source, last_seen"
        placeholders = ",".join("?" * len(top))
        sql = f"SELECT {cols} FROM results WHERE address IN ({placeholders})"  # nosec B608
        rows = self.conn.execute(sql, top).fetchall()
        by_address = {row[0]: row for row in rows}
        return [
            {
                "score": round(fused[a], 4),
                "title": by_address[a][1],
                "onion_url": by_address[a][2],
                "description": by_address[a][3],
                "source": by_address[a][4],
                "last_seen": by_address[a][5],
            }
            for a in top
            if a in by_address
        ]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
