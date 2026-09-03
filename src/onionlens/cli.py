"""Command line interface for OnionLens."""

import argparse
import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Config
from .correlate import correlate
from .extract import extract_entities
from .intel import SOURCE_LABELS, gather_intel
from .models import dedupe
from .pricing import CostMeter
from .safety import is_allowed
from .search import AhmiaSearch
from .store import Store

console = Console()


def _age(stored_at) -> str:
    """Human age of a stored row: how stale a recall hit is."""
    if not stored_at:
        return "?"
    try:
        then = datetime.fromisoformat(stored_at)
    except ValueError:
        return "?"
    days = (datetime.now(timezone.utc) - then).days
    if days <= 0:
        return "today"
    if days < 14:
        return f"{days}d ago"
    if days < 90:
        return f"{days // 7}w ago"
    return f"{days // 30}mo ago"


def _search_hint(query: str, count: int, limit: int) -> str:
    """Tell the user how their query landed and how to change the outcome.

    Ahmia is a full-text engine (Elasticsearch): it matches the words in the
    query against indexed titles and descriptions, ranked by relevance. It does
    OR matching by default, so more words widen the net, not narrow it. There
    is no AND / '+' / boolean operator support, so query craft here is about
    word choice, not syntax.
    """
    terms = [t for t in query.split() if t not in {"+", "-", "AND", "OR"}]
    if count == 0:
        return ("Ahmia found nothing. It matches whole words against indexed "
                "titles/descriptions, so try fewer or more common terms "
                "(one strong keyword beats a long phrase).")
    if count >= limit:
        return (f"Hit the --limit of {limit}; there are likely more. Raise "
                f"--limit or add a distinguishing word to narrow the field.")
    if len(terms) >= 4:
        return (f"{count} results. Ahmia OR-matches every word, so a long query "
                f"like this widens results; drop to the 1-2 strongest keywords "
                f"for a tighter, more relevant set.")
    return f"{count} results for {len(terms)} term(s)."


def _short(address: str) -> str:
    """Compact an onion address for inline display: keep the head and tail."""
    host = address.replace(".onion", "")
    if len(host) <= 20:
        return address
    return f"{host[:10]}…{host[-6:]}.onion"


def _refs(addresses, index) -> str:
    """Render a list of addresses as their result numbers (#1, #2), so long
    onion strings never repeat outside the reference table."""
    out = []
    for a in addresses:
        n = index.get(a)
        out.append(f"[bold]#{n}[/bold]" if n else f"[dim]{_short(a)}[/dim]")
    return ", ".join(out) if out else "[dim](none)[/dim]"


def _render_results(results, unrelated=frozenset()) -> None:
    """Render the result table. Rows the correlator judged unrelated to the
    query (keyword-collision noise) are dimmed so signal reads first."""
    table = Table(title="Indexed onion services", header_style="bold cyan",
                  show_lines=True, expand=True)
    table.add_column("#", style="bold cyan", width=3, justify="right")
    table.add_column("Title", style="bold white", ratio=3, overflow="fold")
    table.add_column("Onion", style="green", ratio=2, no_wrap=True)
    table.add_column("Last seen", style="dim", no_wrap=True, justify="right")
    for i, r in enumerate(results, 1):
        if r.address in unrelated:
            table.add_row(str(i), f"{r.title} (unrelated)", _short(r.address),
                          r.last_seen or "-", style="dim")
        else:
            table.add_row(str(i), r.title, _short(r.address), r.last_seen or "-")
    console.print(table)


def _render_correlation(report: dict, index: dict) -> None:
    if report.get("summary"):
        console.print(Panel(report["summary"], title="[bold]Summary[/bold]",
                            border_style="cyan", padding=(0, 1)))

    clusters = report.get("clusters") or []
    if clusters:
        blocks = []
        for c in clusters:
            blocks.append(
                f"[bold blue]▸ {c.get('theme', '')}[/bold blue]  "
                f"({_refs(c.get('addresses', []), index)})\n"
                f"  {c.get('note', '')}"
            )
        console.print(Panel("\n\n".join(blocks), title="[bold]Clusters[/bold]",
                            border_style="blue", padding=(0, 1)))

    flags = report.get("likely_duplicates_or_scams") or []
    if flags:
        blocks = [
            f"[bold yellow]⚠ {_refs(s.get('addresses', []), index)}[/bold yellow]\n"
            f"  {s.get('reason', '')}"
            for s in flags
        ]
        console.print(Panel("\n\n".join(blocks),
                            title="[bold]Flags: mirrors, duplicates, scams[/bold]",
                            border_style="yellow", padding=(0, 1)))

    followups = report.get("suggested_followups") or []
    if followups:
        console.print(Panel("\n".join(f"[magenta]→[/magenta] {f}" for f in followups),
                            title="[bold]Suggested follow-ups[/bold]",
                            border_style="magenta", padding=(0, 1)))


def _render_reference(results) -> None:
    """Full copy-pasteable addresses, keyed by result number."""
    lines = [f"[cyan]#{i}[/cyan]  [green]{r.address}[/green]"
             for i, r in enumerate(results, 1)]
    console.print(Panel("\n".join(lines), title="[bold]Full addresses[/bold]",
                        border_style="dim", padding=(0, 1)))


def _render_intel(intel) -> None:
    """Compact clearnet context: breaches, reporting, leak-site posts."""
    blocks = []
    for source, records in intel.items():
        lines = [f"• {r.title}  [dim]{r.date or ''}[/dim]" for r in records]
        blocks.append(f"[bold]{SOURCE_LABELS.get(source, source)}[/bold]\n" + "\n".join(lines))
    console.print(Panel("\n\n".join(blocks),
                        title="[bold]Breaches & reporting (clearnet)[/bold]",
                        border_style="red", padding=(0, 1)))


def _render_recall(onion_hits: list[dict], intel_hits: list[dict]) -> None:
    if onion_hits:
        table = Table(title="Knowledge base: onion sightings",
                      header_style="bold cyan", show_lines=True, expand=True)
        table.add_column("Title", style="bold white", ratio=3, overflow="fold")
        table.add_column("Onion", style="green", ratio=2, overflow="fold")
        table.add_column("Stored", style="dim", no_wrap=True, justify="right")
        for hit in onion_hits:
            table.add_row(hit["title"], hit["onion_url"], _age(hit.get("stored_at")))
        console.print(table)
        console.print("[dim]Onion services churn fast; a sighting more than a few "
                      "weeks old is history, not a live address.[/dim]")
    if intel_hits:
        table = Table(title="Knowledge base: breaches & reporting",
                      header_style="bold red", show_lines=True, expand=True)
        table.add_column("Source", style="red", no_wrap=True)
        table.add_column("Title", style="bold white", ratio=3, overflow="fold")
        table.add_column("Date", style="dim", no_wrap=True)
        table.add_column("Stored", style="dim", no_wrap=True, justify="right")
        for hit in intel_hits:
            table.add_row(hit["source"], hit["title"], hit.get("date") or "-",
                          _age(hit.get("stored_at")))
        console.print(table)
    if not onion_hits and not intel_hits:
        console.print("[yellow]No knowledge base matches.[/yellow] The KB grows "
                      "with every search you run.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="onionlens",
        description="AI correlation over onion search engines.",
        epilog="Also: 'onionlens recall <query>' searches the local knowledge "
               "base (past sightings and stored intel) with no network or API cost.")
    p.add_argument("query", help="natural language topic to search for")
    p.add_argument("--limit", type=int, default=25, help="max results to fetch (default 25)")
    p.add_argument("--no-ai", action="store_true", help="skip the AI correlation step")
    p.add_argument("--no-store", action="store_true", help="do not persist results to the local knowledge base")
    p.add_argument("--no-intel", action="store_true", help="skip clearnet intel sources (breaches, news, leak sites)")
    return p


def recall_main(argv) -> int:
    p = argparse.ArgumentParser(
        prog="onionlens recall",
        description="Search the local knowledge base: past onion sightings and "
                    "stored breach intel. Fully local, no network, no API cost.")
    p.add_argument("query", help="topic to recall")
    p.add_argument("--k", type=int, default=15, help="max hits per section (default 15)")
    args = p.parse_args(argv)

    allowed, reason = is_allowed(args.query)
    if not allowed:
        console.print(f"[red]Refused:[/red] {reason}")
        return 2

    store = Store(Config.load())
    try:
        onion_hits = store.search(args.query, k=args.k)
        intel_hits = store.search_intel(args.query, k=args.k)
    finally:
        store.close()
    _render_recall(onion_hits, intel_hits)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["recall"]:
        return recall_main(argv[1:])
    args = build_parser().parse_args(argv)
    config = Config.load()
    meter = CostMeter()

    allowed, reason = is_allowed(args.query)
    if not allowed:
        console.print(f"[red]Refused:[/red] {reason}")
        return 2

    limit = max(1, min(args.limit, config.max_limit))

    engine = AhmiaSearch(config)
    console.print(f"[dim]Searching Ahmia for[/dim] [bold]{args.query}[/bold] ...")
    try:
        results = dedupe(engine.search(args.query, limit=limit))
    except Exception as exc:  # network or parse failure should not crash the tool
        console.print(f"[red]Search failed:[/red] {exc}")
        return 1

    if not results:
        console.print(f"[yellow]No results.[/yellow] {_search_hint(args.query, 0, limit)}")
        return 0

    if engine.degraded:
        console.print("[yellow]Note: parsed via fallback. Ahmia's markup may have "
                      "changed; results could be incomplete (see search/ahmia.py).[/yellow]")

    index = {r.address: i for i, r in enumerate(results, 1)}

    # Clearnet context: breach catalog, breach reporting, ransomware leak sites.
    intel = {}
    if not args.no_intel:
        with console.status("[dim]Checking breach catalogs and reporting ...[/dim]"):
            intel, intel_errors = gather_intel(config, args.query)
        for name, err in intel_errors.items():
            console.print(f"[yellow]Intel source {name} skipped:[/yellow] {err}")

    if not args.no_store:
        # The knowledge base is local FTS5; no API key needed to store results.
        try:
            store = Store(config)
            with console.status("[dim]Indexing locally ...[/dim]"):
                added = store.upsert(results)
                store.upsert_intel([r for recs in intel.values() for r in recs])
            console.print(f"[dim]Stored {added} results (knowledge base holds {store.count()} / {config.max_rows} max).[/dim]")
            store.close()
        except Exception as exc:
            console.print(f"[yellow]Store skipped:[/yellow] {exc}")

    # Correlate before rendering so the table can carry the relevance verdict.
    report = None
    if not args.no_ai:
        if not config.has_anthropic:
            console.print("[yellow]AI correlation skipped: ANTHROPIC_API_KEY not set.[/yellow]")
        else:
            try:
                with console.status("[dim]Correlating ...[/dim]"):
                    report = correlate(config, args.query, results, intel=intel, meter=meter)
            except Exception as exc:
                console.print(f"[yellow]Correlation skipped:[/yellow] {exc}")

    unrelated = set(report.get("unrelated") or []) if report else set()
    _render_results(results, unrelated)
    console.print(f"[dim]{_search_hint(args.query, len(results), limit)}[/dim]")
    if unrelated:
        console.print(f"[dim]{len(unrelated)} result(s) judged unrelated to the "
                      f"query and dimmed above.[/dim]")

    if intel:
        _render_intel(intel)

    # Only surface entities the table does not already show. Onion addresses are
    # in the reference list, so a panel that just repeats them adds no signal;
    # wallets, emails, and PGP blocks are the ones worth calling out.
    blob = " ".join(f"{r.title} {r.description} {r.onion_url}" for r in results)
    entities = {k: v for k, v in extract_entities(blob).items() if k != "onion"}
    if entities:
        console.print(Panel(
            "\n".join(f"[bold]{k}[/bold]: {', '.join(v)}" for k, v in entities.items()),
            title="[bold]Entities found[/bold]", border_style="green", padding=(0, 1)))

    if report is not None:
        _render_correlation(report, index)

    _render_reference(results)
    console.print(f"[dim]Cost this run: {meter.summary()}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
