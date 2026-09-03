"""Clearnet intel sources: passive, public, unauthenticated context feeds."""

from ..config import Config
from ..safety import is_allowed
from .base import IntelRecord, IntelSource
from .hibp import HibpBreaches
from .news import BreachNews
from .ransomwatch import Ransomwatch

SOURCE_LABELS = {
    "hibp": "Known breaches (HIBP)",
    "news": "Recent reporting",
    "ransomwatch": "Ransomware leak sites",
}


def gather_intel(config: Config, query: str) -> tuple[dict[str, list[IntelRecord]], dict[str, str]]:
    """Query every intel source. Returns (records by source, errors by source).

    Each source fails independently: a dead feed reports an error and the rest
    still return. Every record passes the safety gate before it is surfaced.
    """
    records: dict[str, list[IntelRecord]] = {}
    errors: dict[str, str] = {}
    for source in (HibpBreaches(config), BreachNews(config), Ransomwatch(config)):
        try:
            hits = source.search(query, limit=config.max_intel)
        except Exception as exc:
            errors[source.name] = str(exc)
            continue
        hits = [r for r in hits if is_allowed(f"{r.title} {r.summary}")[0]]
        if hits:
            records[source.name] = hits
    return records, errors


__all__ = [
    "IntelRecord",
    "IntelSource",
    "HibpBreaches",
    "BreachNews",
    "Ransomwatch",
    "SOURCE_LABELS",
    "gather_intel",
]
