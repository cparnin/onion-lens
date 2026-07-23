"""Fast local entity extraction.

Runs without any API call so `--no-ai` still returns useful structure. Pulls the
identifiers that matter for correlation: onion addresses, crypto wallets, emails,
and PGP key blocks.
"""

import re

_PATTERNS = {
    "onion": re.compile(r"\b[a-z2-7]{16}(?:[a-z2-7]{40})?\.onion\b", re.IGNORECASE),
    "bitcoin": re.compile(r"\b(?:bc1[a-z0-9]{25,90}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b"),
    "monero": re.compile(r"\b4[0-9AB][0-9a-zA-Z]{93}\b"),
    "email": re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    "pgp": re.compile(r"-----BEGIN PGP (?:PUBLIC KEY|MESSAGE|SIGNATURE)"),
}


def extract_entities(text: str) -> dict[str, list[str]]:
    """Return a dict of entity type to sorted unique matches."""
    found: dict[str, list[str]] = {}
    for name, pattern in _PATTERNS.items():
        matches = pattern.findall(text or "")
        if name == "pgp":
            if matches:
                found[name] = ["present"]
            continue
        unique = sorted({m for m in matches})
        if unique:
            found[name] = unique
    return found
