"""Ransomwatch leak-site tracker.

A community project that scrapes ransomware extortion sites and publishes
victim posts as static JSON on GitHub: {post_title, group_name, discovered}.
Covers the extortion-site slice of the dark web that Ahmia does not index.
The file is large, so it is cached for a day and filtered locally.
"""

from .base import IntelRecord, IntelSource, cached_get_json, match_score, query_terms


class Ransomwatch(IntelSource):
    name = "ransomwatch"

    def search(self, query: str, limit: int = 8) -> list[IntelRecord]:
        posts = cached_get_json(
            self.cfg,
            self.cfg.ransomwatch_url,
            "ransomwatch_posts.json",
            self.cfg.intel_cache_ttl,
        )
        terms = query_terms(query)
        scored = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            title = post.get("post_title") or ""
            score = match_score(terms, title)
            if score:
                scored.append((score, post.get("discovered") or "", post))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [
            IntelRecord(
                source=self.name,
                title=post.get("post_title") or "(untitled)",
                summary=f"Listed as a victim on the {post.get('group_name') or 'unknown'} "
                        f"ransomware leak site.",
                date=(post.get("discovered") or "")[:10] or None,
            )
            for _, _, post in scored[:limit]
        ]
