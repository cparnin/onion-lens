"""Search engine adapters. Each engine implements the SearchEngine interface."""

from .base import SearchEngine
from .ahmia import AhmiaSearch

__all__ = ["SearchEngine", "AhmiaSearch"]
