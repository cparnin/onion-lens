# CLAUDE.md

Conventions for working in this repository. Follow them for every change.

## What this is

OnionLens is a passive OSINT tool: an AI correlation layer over existing onion
search engines (Ahmia today). It reads publicly indexed metadata. It does not
crawl, authenticate, transact, or fetch content behind access walls.

## Hard rules

- **No em dashes.** Anywhere: code, comments, docs, commit messages. Use commas,
  parentheses, colons, or separate sentences.
- **Zero tolerance for abuse material.** The safety gate in `src/onionlens/safety.py`
  must stay in the path of every query and every result. Do not add a source that
  lacks upstream filtering without also adding content filtering. See
  `docs/security.md`.
- **Passive only.** Do not add features that log into sites, buy access, or fetch
  gated content.

## Secrets

- The OpenAI key lives in a gitignored `.env`. Never commit it. Never add it as a
  GitHub secret unless a workflow genuinely needs it (CI here does not).

## Testing and checks

- Every change ships with tests. Run `make test` (pytest) and `make security`
  (bandit + pip-audit) before committing.
- Logic tests use the fake OpenAI client in `tests/conftest.py`, so they need no
  key and no network. Keep it that way; do not make the test suite call live APIs.

## Docs

- Keep docs concise and current. When behavior changes, update `README.md` and the
  relevant file in `docs/` in the same change.

## Cost and size discipline

- Keep the OpenAI cost bounded: respect `max_correlate`, the `--limit` ceiling,
  and truncated inputs. Every run reports real cost via the CostMeter.
- Keep the knowledge base bounded: `max_rows` with pruning on write. Do not remove
  the cap.

## Architecture

- Pipeline and stage responsibilities are in `docs/architecture.md`. New search
  engines implement `SearchEngine` in `src/onionlens/search/base.py` and change
  nothing downstream. Torch is the next planned engine (`docs/roadmap.md`).
