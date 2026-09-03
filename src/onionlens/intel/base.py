"""Intel source interface and shared helpers.

Intel sources are clearnet context feeds (breach catalogs, breach reporting,
ransomware leak-site trackers). They are not onion search engines: their
records have no onion address, so they live in their own table and are fed to
correlation as labeled context, never mixed into the numbered result list.

All sources are passive: public, unauthenticated HTTP GETs. Responses are
cached on disk with a TTL so repeated runs cost one fetch per day, and a stale
cache is served when the network fails, so intel degrades instead of breaking
the run.
"""

import hashlib
import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import requests

from ..config import Config

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class IntelRecord:
    source: str
    title: str
    summary: str
    date: Optional[str] = None
    url: str = ""

    @property
    def key(self) -> str:
        """Stable dedupe key: the URL when there is one, else a title hash."""
        if self.url:
            return self.url
        digest = hashlib.sha256(f"{self.source}:{self.title}".encode()).hexdigest()
        return f"{self.source}:{digest[:16]}"


class IntelSource(ABC):
    name: str = "base"

    def __init__(self, config: Config):
        self.cfg = config

    @abstractmethod
    def search(self, query: str, limit: int = 8) -> list[IntelRecord]:
        """Return records matching the query, best first."""
        raise NotImplementedError


def strip_tags(text: str) -> str:
    return _TAG_RE.sub("", text or "").strip()


def query_terms(query: str) -> set[str]:
    """Lowercase word terms worth matching, plus naive singulars so
    'licenses' also matches 'license'."""
    terms = {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 3}
    return terms | {t[:-1] for t in terms if len(t) > 4 and t.endswith("s")}


def match_score(terms: set[str], text: str) -> int:
    text = (text or "").lower()
    return sum(1 for t in terms if t in text)


def _cache_path(cfg: Config, name: str) -> str:
    base = os.path.join(
        os.path.dirname(os.path.abspath(cfg.db_path)), ".onionlens_cache"
    )
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, name)


def cached_get_text(cfg: Config, url: str, cache_name: str, ttl: int) -> str:
    """GET with an on-disk TTL cache. A stale cache is better than a failed
    run, so it is served when the fetch raises."""
    path = _cache_path(cfg, cache_name)
    fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl
    if fresh:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": cfg.user_agent},
            timeout=cfg.request_timeout,
        )
        resp.raise_for_status()
    except Exception:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        raise
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(resp.text)
    return resp.text


def cached_get_json(cfg: Config, url: str, cache_name: str, ttl: int):
    return json.loads(cached_get_text(cfg, url, cache_name, ttl))
