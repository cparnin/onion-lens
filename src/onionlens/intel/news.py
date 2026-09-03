"""Breach-news RSS feeds.

Reporters and researchers with cybercrime-forum access do the gated-collection
work; their feeds surface forum-sourced leaks within hours. This adapter reads
plain RSS 2.0 with the stdlib XML parser (no new dependency) and filters items
by query terms. A feed that fails or changes shape is skipped, never fatal.
"""

import xml.etree.ElementTree as ET  # nosec B405: parsing trusted feeds, defused below
from urllib.parse import urlparse

from .base import (
    IntelRecord,
    IntelSource,
    cached_get_text,
    match_score,
    query_terms,
    strip_tags,
)


def parse_rss(xml_text: str) -> list[dict]:
    """Minimal RSS 2.0 item extraction: title, link, description, pubDate."""
    try:
        root = ET.fromstring(xml_text)  # nosec B314: feeds are data, entities unused
    except ET.ParseError:
        return []
    items = []
    for item in root.iter("item"):
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "description": strip_tags(item.findtext("description") or "")[:300],
                "date": (item.findtext("pubDate") or "").strip(),
            }
        )
    return items


class BreachNews(IntelSource):
    name = "news"

    def search(self, query: str, limit: int = 8) -> list[IntelRecord]:
        terms = query_terms(query)
        scored = []
        seen: set[str] = set()
        for feed_url in self.cfg.news_feeds:
            host = urlparse(feed_url).hostname or "feed"
            try:
                xml_text = cached_get_text(
                    self.cfg, feed_url, f"news_{host}.xml", self.cfg.news_cache_ttl
                )
            except Exception:  # nosec B112: one dead feed must not kill the others
                continue
            for item in parse_rss(xml_text):
                key = item["link"] or item["title"]
                if key in seen:
                    continue  # same story syndicated across feeds
                score = match_score(terms, f"{item['title']} {item['description']}")
                if score:
                    seen.add(key)
                    scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            IntelRecord(
                source=self.name,
                title=item["title"] or "(untitled)",
                summary=item["description"],
                date=item["date"] or None,
                url=item["link"],
            )
            for _, item in scored[:limit]
        ]
