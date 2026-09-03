"""Rendering behavior: unrelated results are dimmed, not hidden, and keep
their original numbering so correlation prose stays aligned."""

from io import StringIO

from rich.console import Console

import onionlens.cli as cli
from onionlens.models import SearchResult


def make(n):
    return [
        SearchResult(
            title=f"site{i}",
            onion_url=f"http://{'a' * 10}{i}.onion",
            description="x",
            source="ahmia",
        )
        for i in range(n)
    ]


def render(results, unrelated=frozenset(), width=120):
    buf = StringIO()
    original = cli.console
    cli.console = Console(file=buf, width=width, force_terminal=False)
    try:
        cli._render_results(results, unrelated)
    finally:
        cli.console = original
    return buf.getvalue()


def test_render_marks_unrelated_rows():
    results = make(3)
    out = render(results, unrelated={results[1].address})
    assert "site1 (unrelated)" in out
    assert "site0 (unrelated)" not in out
    assert "site2 (unrelated)" not in out


def test_render_keeps_all_rows_and_numbering():
    results = make(3)
    out = render(results, unrelated={results[0].address, results[2].address})
    for i in range(3):
        assert f"site{i}" in out


def test_render_without_verdicts_is_unchanged():
    out = render(make(2))
    assert "(unrelated)" not in out


def test_age_buckets():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    assert cli._age(None) == "?"
    assert cli._age("garbage") == "?"
    assert cli._age(now.isoformat(timespec="seconds")) == "today"
    assert cli._age((now - timedelta(days=3)).isoformat()) == "3d ago"
    assert cli._age((now - timedelta(days=21)).isoformat()) == "3w ago"
    assert cli._age((now - timedelta(days=120)).isoformat()) == "4mo ago"


def test_render_recall_shows_age_and_staleness_note():
    buf = StringIO()
    original = cli.console
    cli.console = Console(file=buf, width=120, force_terminal=False)
    try:
        cli._render_recall(
            [{"title": "old vendor", "onion_url": "http://a.onion",
              "stored_at": None}],
            [{"source": "hibp", "title": "BigID Leak", "date": "2026-08-01",
              "stored_at": None}],
        )
        cli._render_recall([], [])
    finally:
        cli.console = original
    out = buf.getvalue()
    assert "old vendor" in out and "BigID Leak" in out
    assert "history, not a live address" in out
    assert "No knowledge base matches" in out


def test_render_intel_panel():
    from onionlens.intel.base import IntelRecord

    buf = StringIO()
    original = cli.console
    cli.console = Console(file=buf, width=120, force_terminal=False)
    try:
        cli._render_intel({"hibp": [IntelRecord(
            source="hibp", title="BigID Leak", summary="x", date="2026-08-01")]})
    finally:
        cli.console = original
    out = buf.getvalue()
    assert "Known breaches (HIBP)" in out and "BigID Leak" in out
