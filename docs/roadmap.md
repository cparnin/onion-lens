# Roadmap

## v0.1 (now)
- Ahmia clearnet adapter
- Safety gate and per-result screening
- Local entity extraction
- SQLite FTS5 + local embedding knowledge base
- Claude correlation
- Rich CLI

## Next: add Torch as a second engine
Torch is one of the largest onion indexes and complements Ahmia's cleaner but
narrower coverage.

Key differences from Ahmia to plan for:
- **Onion only.** Torch has no clearnet endpoint, so it requires a Tor SOCKS
  proxy. To keep Tor off the primary machine, run Tor on a separate box (for
  example a Windows machine on the LAN) and point the adapter at that host's
  SOCKS port. Configure via a `TOR_SOCKS_PROXY` env var, for example
  `socks5h://192.168.1.50:9050`.
- **No API key needed.** Torch is free to query. The only requirement is routing
  through Tor. (Haystak, listed under Later, is the one with a paid API.)
- **Unfiltered.** Torch does not filter abuse material. The safety gate must stay
  in the path. By design the gate blocks only CSAM-category content; all other
  material (markets, fraud, breach data, and so on) passes through untouched. A
  hash-based image filter should be added before Torch is enabled by default so
  that no child content is ever shown.
- **Noisier index.** Expect more duplicates, ads, and dead links. Lean on the
  existing dedupe and on the AI scam/duplicate flagging.

Implementation: add `search/torch.py` implementing `SearchEngine`, route its
requests through the Tor proxy, and register it behind a `--engines` flag so
users opt in. No changes needed downstream.

## Later
- Interactive REPL for iterative querying against the knowledge base
- Scheduled monitoring with alerts on new matches for saved queries
- Optional page fetching (through Tor) for surface pages that are not gated
- Additional engines (Haystak API, OnionLand) behind the same interface
- Optional local model support to remove API cost entirely
