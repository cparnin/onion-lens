"""Search engine interface.

Every source (Ahmia today, Torch later) implements this so the rest of the
pipeline never needs to know which engine produced a result. Adding an engine
means writing one adapter, not touching the correlation layer.
"""

from abc import ABC, abstractmethod

from ..models import SearchResult


class SearchEngine(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, limit: int = 25) -> list[SearchResult]:
        """Return safety-screened results for a query."""
        raise NotImplementedError
