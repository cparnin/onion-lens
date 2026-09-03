"""Runtime configuration, loaded from environment or a local .env file."""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; env vars still work without it
    pass


@dataclass
class Config:
    anthropic_api_key: str
    chat_model: str = "claude-haiku-4-5"
    ahmia_base_url: str = "https://ahmia.fi"
    request_timeout: int = 20
    user_agent: str = (
        "Mozilla/5.0 (compatible; OnionLens/0.1; research tool)"
    )
    rate_limit_seconds: float = 1.0
    db_path: str = "onionlens.db"

    # Guardrails
    max_rows: int = 5000       # hard cap on knowledge base size; oldest pruned
    max_correlate: int = 40    # max results sent to the AI per run
    max_limit: int = 100       # ceiling on --limit regardless of what is passed

    # Intel sources (clearnet context feeds; all public and unauthenticated)
    hibp_url: str = "https://haveibeenpwned.com/api/v3/breaches"
    ransomwatch_url: str = (
        "https://raw.githubusercontent.com/joshhighet/ransomwatch/main/posts.json"
    )
    news_feeds: tuple = (
        "https://databreaches.net/feed/",
        "https://www.bleepingcomputer.com/feed/",
    )
    max_intel: int = 8          # per-source cap on records shown and sent to the AI
    max_intel_rows: int = 500   # per-source cap in the knowledge base; oldest pruned
    intel_cache_ttl: int = 86400  # catalogs change daily at most
    news_cache_ttl: int = 3600    # feeds move faster

    @classmethod
    def load(cls) -> "Config":
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            chat_model=os.getenv("ONIONLENS_CHAT_MODEL", "claude-haiku-4-5"),
            db_path=os.getenv("ONIONLENS_DB", "onionlens.db"),
            max_rows=int(os.getenv("ONIONLENS_MAX_ROWS", "5000")),
        )

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)
