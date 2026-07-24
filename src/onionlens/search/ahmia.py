"""Ahmia adapter.

Ahmia runs on the clearnet, so this needs no Tor. It filters abuse material
upstream; we screen again locally as defense in depth.

This is the most fragile part of the project: it depends on Ahmia's website not
changing. Three defenses reduce the blast radius of a change:

1. Ahmia plants a hidden per-session token in its search form. A request without
   it is redirected to the homepage. We fetch the form first and echo the token
   back, and we detect a bounce so the failure is a clear message, not empty
   results.
2. Parsing has a fallback: if the result container class changes, we still
   extract results from the redirect anchors that Ahmia uses on every hit.
3. When the fallback is used, `degraded` is set so the CLI can warn that the
   markup likely changed and this file may need a look.

If Ahmia changes its markup, only this file needs updating.
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
        self._tokens: dict | None = None
        self.degraded = False  # set when the parse fallback was needed

    @staticmethod
    def parse_tokens(html: str) -> dict:
        """Extract hidden form inputs (the anti-scrape token) from a page."""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.select_one("form#searchForm") or soup.select_one("form")
        tokens: dict = {}
        if form:
            for inp in form.select("input[type=hidden]"):
                name = inp.get("name")
                if name:
                    tokens[name] = inp.get("value", "")
        return tokens

    def _get_tokens(self) -> dict:
        if self._tokens is None:
            resp = self.session.get(
                f"{self.cfg.ahmia_base_url}/", timeout=self.cfg.request_timeout
            )
            resp.raise_for_status()
            self._tokens = self.parse_tokens(resp.text)
        return self._tokens

    def search(self, query: str, limit: int = 25) -> list[SearchResult]:
        allowed, _ = is_allowed(query)
        if not allowed:
            return []
        params = {"q": query, **self._get_tokens()}
        resp = self.session.get(
            f"{self.cfg.ahmia_base_url}/search/",
            params=params,
            timeout=self.cfg.request_timeout,
        )
        resp.raise_for_status()
        # Detect the "bounced to homepage" failure mode explicitly.
        if "search" not in urlparse(str(resp.url)).path:
            raise RuntimeError(
                "Ahmia redirected away from the search page; its form token or "
                "endpoint likely changed. Check src/onionlens/search/ahmia.py."
            )
        time.sleep(self.cfg.rate_limit_seconds)  # be a good citizen
        return self.parse(resp.text, limit)

    def parse(self, html: str, limit: int = 25) -> list[SearchResult]:
        self.degraded = False
        soup = BeautifulSoup(html, "html.parser")

        items = soup.select("li.result")
        if items:
            results = self._from_items(items, limit)
            if results:
                return results

        # Fallback: container markup may have changed. Extract from the redirect
        # anchors Ahmia uses on every result. Degraded but still useful.
        anchors = soup.select('a[href*="redirect_url="]')
        if anchors:
            results = self._from_anchors(anchors, limit)
            if results:
                self.degraded = True
                return results

        return []

    def _from_items(self, items, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        for item in items:
            link = item.select_one("h4 a") or item.select_one("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            onion = self._extract_onion(link.get("href", ""), item)
            if not onion:
                continue

            desc_el = item.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""
            last_seen = self._extract_last_seen(item)

            if not self._screen(title, description, onion):
                continue
            results.append(self._build(title, onion, description, last_seen))
            if len(results) >= limit:
                break
        return results

    def _from_anchors(self, anchors, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen: set[str] = set()
        for link in anchors:
            onion = self._extract_onion(link.get("href", ""), None)
            if not onion or onion in seen:
                continue
            title = link.get_text(strip=True) or "(untitled)"
            if not self._screen(title, "", onion):
                continue
            seen.add(onion)
            results.append(self._build(title, onion, "", None))
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _screen(title: str, description: str, onion: str) -> bool:
        allowed, _ = is_allowed(f"{title} {description} {onion}")
        return allowed

    @staticmethod
    def _build(title, onion, description, last_seen) -> SearchResult:
        return SearchResult(
            title=title or "(untitled)",
            onion_url=onion,
            description=description,
            source="ahmia",
            last_seen=last_seen,
        )

    @staticmethod
    def _extract_last_seen(item):
        el = item.select_one(".lastSeen")
        if not el:
            return None
        # Prefer the concise relative label, then absolute attributes.
        value = (
            el.get_text(strip=True)
            or el.get("data-timestamp")
            or el.get("datetime")
        )
        # Ahmia uses non-breaking spaces in the relative label.
        return value.replace("\xa0", " ") if value else None

    @staticmethod
    def _extract_onion(href: str, item) -> str:
        # Ahmia result links pass through /search/redirect?...&redirect_url=<onion>
        if "redirect_url=" in href:
            qs = parse_qs(urlparse(href).query)
            if qs.get("redirect_url"):
                return unquote(qs["redirect_url"][0])
        if item is not None:
            cite = item.select_one("cite")
            if cite:
                return cite.get_text(strip=True)
        if ".onion" in href:
            return href
        return ""
