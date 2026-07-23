"""Core data types shared across the pipeline."""

from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urlparse


@dataclass
class SearchResult:
    title: str
    onion_url: str
    description: str
    source: str
    last_seen: Optional[str] = None

    @property
    def address(self) -> str:
        """Bare onion host, used as the dedupe key across engines."""
        parsed = urlparse(self.onion_url if "//" in self.onion_url else f"//{self.onion_url}")
        host = (parsed.hostname or self.onion_url).lower()
        return host

    def to_dict(self) -> dict:
        data = asdict(self)
        data["address"] = self.address
        return data


def dedupe(results: list["SearchResult"]) -> list["SearchResult"]:
    """Keep the first result per onion address, preserving order."""
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for result in results:
        key = result.address
        if key and key not in seen:
            seen.add(key)
            unique.append(result)
    return unique
