"""Content safety gate.

OnionLens refuses to index, store, or surface child sexual abuse material
(CSAM) or related content under any circumstances. Ahmia already filters most
of this upstream; this module is defense in depth and also blocks abuse-category
queries before any network call is made.

The gate is intentionally simple and conservative: it errs toward blocking. It
is not a replacement for upstream filtering, and users should not point the tool
at unfiltered sources without keeping this gate in place.
"""

import re

# Category markers for content we refuse to touch. These are moderation labels,
# not a search vocabulary. Extend via a local override if needed.
_BLOCKED_PATTERNS = [
    r"\bcsam\b",
    r"child\s*(porn|pornography|abuse|exploitation|exploit)",
    r"\bchildporn\b",
    r"\bpedo(phile|philia)?\b",
    r"\bp[\W_]?e[\W_]?d[\W_]?o\b",
    r"\bunderage\b",
    r"\bjailbait\b",
    r"\blolita\b",
    r"\bpreteen\b",
    r"\bcp\s*(vids?|videos?|pics?|content)\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]


def is_allowed(text: str) -> tuple[bool, str]:
    """Return (allowed, reason). reason is empty when allowed."""
    for pattern in _COMPILED:
        if pattern.search(text or ""):
            return False, "blocked: abuse-category content is not permitted"
    return True, ""
