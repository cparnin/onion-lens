"""Have I Been Pwned breach catalog.

The /breaches endpoint is free and unauthenticated: structured metadata for
every publicized breach (name, date, record count, data classes). One fetch
returns the whole catalog, so it is cached for a day and filtered locally.
"""

from .base import (
    IntelRecord,
    IntelSource,
    cached_get_json,
    match_score,
    query_terms,
    strip_tags,
)


class HibpBreaches(IntelSource):
    name = "hibp"

    def search(self, query: str, limit: int = 8) -> list[IntelRecord]:
        breaches = cached_get_json(
            self.cfg, self.cfg.hibp_url, "hibp_breaches.json", self.cfg.intel_cache_ttl
        )
        terms = query_terms(query)
        scored = []
        for b in breaches:
            if not isinstance(b, dict):
                continue
            text = " ".join(
                [
                    b.get("Title") or "",
                    b.get("Name") or "",
                    strip_tags(b.get("Description") or ""),
                    " ".join(b.get("DataClasses") or []),
                ]
            )
            score = match_score(terms, text)
            if score:
                scored.append((score, b.get("BreachDate") or "", b))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

        records = []
        for _, _, b in scored[:limit]:
            name = b.get("Title") or b.get("Name") or "(unnamed breach)"
            count = b.get("PwnCount") or 0
            classes = ", ".join((b.get("DataClasses") or [])[:6])
            summary = strip_tags(b.get("Description") or "")[:300]
            if classes:
                summary = f"[{classes}] {summary}"
            records.append(
                IntelRecord(
                    source=self.name,
                    title=f"{name}: {count:,} accounts" if count else name,
                    summary=summary,
                    date=b.get("BreachDate"),
                    url=f"https://haveibeenpwned.com/breach/{b.get('Name') or ''}",
                )
            )
        return records
