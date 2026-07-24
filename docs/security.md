# Security and safety

## Zero tolerance for abuse material

OnionLens refuses to index, store, or surface child sexual abuse material (CSAM)
or related content. This is non-negotiable and enforced in two layers:

1. **Upstream.** Ahmia filters this content and is the only enabled source in
   v0.1.
2. **Local gate** (`safety.py`). The query is screened before any network call,
   and every individual result is screened again before it can be stored or sent
   to the AI. The gate errs toward blocking.

If a future engine (for example Torch) is added, it must not be enabled by
default without a hash-based image filter in addition to the text gate.

## Handling secrets

- The OpenAI key is read from `OPENAI_API_KEY`, loaded from a gitignored `.env`.
- `.env` and the local `*.db` knowledge base are gitignored and must never be
  committed.

## Network hygiene

- Ahmia is reached over clearnet HTTPS only. No Tor is bundled or required.
- Requests are rate limited and send a descriptive User-Agent.
- OnionLens is passive. It reads indexed metadata. It does not authenticate to
  sites, transact, or fetch content behind access walls.

## Automated checks

CI runs on every push and pull request:

- `bandit` for static analysis of the Python source
- `pip-audit` for known vulnerabilities in dependencies
- `pytest` for the test suite, including safety-gate tests

Run them locally:

```bash
pip install -e ".[dev]"
bandit -r src
pip-audit
pytest
```

## Automated maintenance

Dependabot (`.github/dependabot.yml`) opens weekly pull requests to update Python
dependencies and GitHub Actions versions. CI and the security scan run against
each of those pull requests, so the project stays current and patched even if it
is left untouched for months. Review and merge the pull requests, or enable
auto-merge in the repository settings for a fully hands-off flow.

## Reporting

Found a security or safety issue? Open a private report to the repository owner
rather than a public issue.
