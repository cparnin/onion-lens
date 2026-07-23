"""Ahmia adapter.

Ahmia runs on the clearnet, so this needs no Tor. It filters abuse material
upstream; we screen again locally as defense in depth. Parsing is deliberately
defensive because a search engine's HTML can change without notice. If Ahmia
changes its markup, only this file needs updating.
"""

import time
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .base import SearchEngine
from ..config import Config
from ..models import SearchResult
from ..safety import is_allowed


class AhmiaSearch(SearchEngine):
    name = "ahmia"

    def __init__(self, config: Config):
        self.cfg = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})

    def search(self, query: str, limit: int = 25) -> list[SearchResult]:
        allowed, _ = is_allowed(query)
        if not allowed:
            return []
        resp = self.session.get(
            f"{self.cfg.ahmia_base_url}/search/",
            params={"q": query},
            timeout=self.cfg.request_timeout,
        )
        resp.raise_for_status()
        time.sleep(self.cfg.rate_limit_seconds)  # be a good citizen
        return self.parse(resp.text, limit)

    def parse(self, html: str, limit: int = 25) -> list[SearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[SearchResult] = []

        for item in soup.select("li.result"):
            link = item.select_one("h4 a") or item.select_one("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            onion = self._extract_onion(link.get("href", ""), item)
            if not onion:
                continue

            desc_el = item.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""
            seen_el = item.select_one(".lastSeen")
            last_seen = seen_el.get("datetime") if seen_el else None

            allowed, _ = is_allowed(f"{title} {description} {onion}")
            if not allowed:
                continue

            results.append(
                SearchResult(
                    title=title or "(untitled)",
                    onion_url=onion,
                    description=description,
                    source=self.name,
                    last_seen=last_seen,
                )
            )
            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _extract_onion(href: str, item) -> str:
        # Ahmia result links pass through /search/redirect?...&redirect_url=<onion>
        if "redirect_url=" in href:
            qs = parse_qs(urlparse(href).query)
            if qs.get("redirect_url"):
                return unquote(qs["redirect_url"][0])
        cite = item.select_one("cite")
        if cite:
            return cite.get_text(strip=True)
        if ".onion" in href:
            return href
        return ""
