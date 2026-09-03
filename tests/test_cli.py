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
