"""Persistent knowledge base.

Stores every result plus its embedding in a local SQLite file so correlation can
work across sessions, not just within one query. Vector similarity uses numpy
cosine over stored embeddings, which is instant at personal scale and keeps the
dependency list small (no vector database needed).
"""

import json
import sqlite3
import struct
from typing import Optional

import numpy as np

from .config import Config
from .models import SearchResult


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes) -> np.ndarray:
    count = len(blob) // 4
    return np.array(struct.unpack(f"{count}f", blob), dtype=np.float32)


class Store:
    def __init__(self, config: Config, client=None):
        self.cfg = config
        self._client = client  # injectable for testing
        self.conn = sqlite3.connect(config.db_path)
        self._init_db()

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.cfg.openai_api_key)
        return self._client

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
        self.conn.commit()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=self.cfg.embedding_model, input=texts)
        return [d.embedding for d in resp.data]

    def upsert(self, results: list[SearchResult]) -> int:
        if not results:
            return 0
        texts = [f"{r.title}. {r.description}" for r in results]
        vectors = self._embed(texts)
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
                    _pack(vec),
                ),
            )
        self.conn.commit()
        return len(results)

    def semantic_search(self, query: str, k: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT address, title, onion_url, description, source, last_seen, embedding FROM results"
        ).fetchall()
        if not rows:
            return []
        query_vec = np.array(self._embed([query])[0], dtype=np.float32)
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)

        scored = []
        for row in rows:
            vec = _unpack(row[6])
            vec = vec / (np.linalg.norm(vec) + 1e-9)
            score = float(np.dot(query_norm, vec))
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "score": round(score, 4),
                "title": row[1],
                "onion_url": row[2],
                "description": row[3],
                "source": row[4],
                "last_seen": row[5],
            }
            for score, row in scored[:k]
        ]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]

    def close(self) -> None:
        self.conn.close()
