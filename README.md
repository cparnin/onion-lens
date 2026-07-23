# OnionLens

An AI correlation layer over existing onion search engines. Ask in plain
English, get back correlated findings instead of a raw keyword dump.

OnionLens does not crawl the dark web. It piggybacks on
[Ahmia](https://ahmia.fi), a clearnet search engine that already indexes and
filters onion services, then adds the part the existing engines lack: an AI pass
that clusters results, extracts shared entities, flags likely scam or mirror
duplicates, and suggests follow-up searches.

## What it is and is not

- It is a passive OSINT and threat-intelligence lens. It reads publicly indexed
  metadata (titles, descriptions, addresses).
- It finds **where** something lives and what it claims to be. It does not log
  into anything or view content behind registration or paywalls.
- It never touches child sexual abuse material. See [Safety](#safety).

## How it works

```
your query
  -> Ahmia (clearnet, no Tor needed)
  -> safety screen + dedupe
  -> local entity extraction (wallets, emails, PGP, onion links)
  -> persistent knowledge base (SQLite + embeddings)
  -> AI correlation (OpenAI): clusters, entities, likely duplicates, follow-ups
```

Full diagram in [docs/architecture.md](docs/architecture.md).

## Install

Requires Python 3.10+.

```bash
git clone <your-repo-url>
cd onion-lens
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env      # then paste your OpenAI key into .env
```

No Tor is required. Ahmia is reached over normal HTTPS.

## Usage

```bash
onionlens "ransomware leak sites"
onionlens "vendor handle acme" --limit 40
onionlens "breach forum" --no-ai      # skip the AI step, still get results + entities
```

Every run stores results in a local `onionlens.db` so correlation improves as
your knowledge base grows across sessions.

## Cost and size guardrails

Using OpenAI with the default models (`gpt-4o-mini` + `text-embedding-3-small`),
a typical query costs well under a cent. Heavy daily use lands in the low single
digits of dollars per month. Every run prints exactly what it cost.

Built-in limits keep both the bill and the database bounded:

- `--limit` caps results fetched per run (default 25, hard ceiling 100).
- Only the first `max_correlate` results (default 40) are sent to the AI, and
  descriptions are truncated, so per-run token cost is bounded.
- The knowledge base is capped at `max_rows` (default 5000, set via
  `ONIONLENS_MAX_ROWS`). Oldest rows are pruned on every write, so the SQLite
  file cannot run away. At the default cap the database stays around 30-40 MB.

## Safety

OnionLens refuses to index, store, or surface CSAM under any circumstances. Two
layers enforce this: Ahmia filters upstream, and a local gate blocks
abuse-category queries and results before storage or AI. Details in
[docs/security.md](docs/security.md).

## Roadmap

Torch and other sources, an interactive REPL, and scheduled monitoring are
planned. See [docs/roadmap.md](docs/roadmap.md).

## Legal and ethical use

This tool is for authorized security research, threat intelligence, and OSINT.
You are responsible for complying with the laws and policies that apply to you.
Do not use it to access, transact in, or participate in criminal activity.

## License

MIT. See [LICENSE](LICENSE).
