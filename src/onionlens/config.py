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
    openai_api_key: str
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
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

    @classmethod
    def load(cls) -> "Config":
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            chat_model=os.getenv("ONIONLENS_CHAT_MODEL", "gpt-4o-mini"),
            embedding_model=os.getenv("ONIONLENS_EMBED_MODEL", "text-embedding-3-small"),
            db_path=os.getenv("ONIONLENS_DB", "onionlens.db"),
            max_rows=int(os.getenv("ONIONLENS_MAX_ROWS", "5000")),
        )

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)
