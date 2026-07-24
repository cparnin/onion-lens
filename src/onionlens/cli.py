"""Command line interface for OnionLens."""

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import Config
from .correlate import correlate
from .extract import extract_entities
from .models import dedupe
from .pricing import CostMeter
from .safety import is_allowed
from .search import AhmiaSearch
from .store import Store

console = Console()


def _render_results(results) -> None:
    # show_lines + overflow="fold" so long onion addresses wrap in full and stay
    # copy-pasteable instead of being truncated to fit the terminal width.
    table = Table(title="Indexed onion services", header_style="bold cyan", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold", max_width=34, overflow="fold")
    table.add_column("Onion address", style="green", overflow="fold")
    table.add_column("Last seen", style="dim", no_wrap=True)
    for i, r in enumerate(results, 1):
        table.add_row(str(i), r.title, r.address, r.last_seen or "-")
    console.print(table)


def _render_correlation(report: dict) -> None:
    if report.get("summary"):
        console.print(Panel(report["summary"], title="AI summary", border_style="cyan"))
    for c in report.get("clusters") or []:
        body = f"[bold]{c.get('theme', '')}[/bold]\n{c.get('note', '')}\n" + "\n".join(
            f"  - {a}" for a in c.get("addresses", [])
        )
        console.print(Panel(body, border_style="blue", title="cluster"))
    for s in report.get("likely_duplicates_or_scams") or []:
        console.print(
            Panel(
                f"{', '.join(s.get('addresses', []))}\n{s.get('reason', '')}",
                title="possible duplicate or scam",
                border_style="yellow",
            )
        )
    followups = report.get("suggested_followups") or []
    if followups:
        console.print(Panel("\n".join(f"- {f}" for f in followups),
                            title="suggested follow-ups", border_style="magenta"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="onionlens", description="AI correlation over onion search engines.")
    p.add_argument("query", help="natural language topic to search for")
    p.add_argument("--limit", type=int, default=25, help="max results to fetch (default 25)")
    p.add_argument("--no-ai", action="store_true", help="skip the AI correlation step")
    p.add_argument("--no-store", action="store_true", help="do not persist results to the local knowledge base")
    return p


def main(argv=None) -> int:
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
        console.print("[yellow]No results found.[/yellow]")
        return 0

    _render_results(results)

    blob = " ".join(f"{r.title} {r.description} {r.onion_url}" for r in results)
    entities = extract_entities(blob)
    if entities:
        console.print(Panel("\n".join(f"[bold]{k}[/bold]: {', '.join(v)}" for k, v in entities.items()),
                            title="entities found", border_style="green"))

    if not args.no_store:
        if config.has_openai:
            try:
                store = Store(config)
                added = store.upsert(results, meter)
                console.print(f"[dim]Stored {added} results (knowledge base holds {store.count()} / {config.max_rows} max).[/dim]")
                store.close()
            except Exception as exc:
                console.print(f"[yellow]Store skipped:[/yellow] {exc}")
        else:
            console.print("[yellow]Store skipped: OPENAI_API_KEY not set.[/yellow]")

    if not args.no_ai:
        if not config.has_openai:
            console.print("[yellow]AI correlation skipped: OPENAI_API_KEY not set.[/yellow]")
        else:
            console.print("[dim]Correlating ...[/dim]")
            try:
                report = correlate(config, args.query, results, meter=meter)
                _render_correlation(report)
            except Exception as exc:
                console.print(f"[yellow]Correlation skipped:[/yellow] {exc}")

    console.print(f"[dim]Cost this run: {meter.summary()}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
