"""AI correlation layer.

Takes the raw result list and asks the model to do what the existing engines
cannot: cluster by theme, pull out shared entities, flag likely mirror or scam
duplicates, and suggest follow-up searches. Returns structured JSON.

Input is capped at config.max_correlate and descriptions are truncated, so the
per-run token cost stays bounded no matter how many results were fetched.
"""

import json

from .config import Config
from .models import SearchResult
from .pricing import CostMeter

_SYSTEM = """You are a threat-intelligence analyst assistant. You are given
metadata (titles, descriptions, onion addresses) from dark web search engines.
Your job is passive correlation of publicly indexed metadata only.

Rules:
- Never produce, request, or assist with sexual content involving minors or any
  other illegal material. If the input contains it, exclude it and note the
  exclusion.
- Work only from the provided metadata. Do not invent onion addresses, handles,
  or facts.
- Focus on connections: shared operators, mirrored sites, reused handles or
  keys, and probable scams or phishing clones.

Return strict JSON with this shape:
{
  "summary": string,
  "clusters": [{"theme": string, "addresses": [string], "note": string}],
  "entities": {"handles": [string], "wallets": [string], "emails": [string]},
  "likely_duplicates_or_scams": [{"addresses": [string], "reason": string}],
  "suggested_followups": [string]
}"""

_EMPTY = {
    "summary": "",
    "clusters": [],
    "entities": {},
    "likely_duplicates_or_scams": [],
    "suggested_followups": [],
}


def _compact(results: list[SearchResult]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title[:120]} | {r.address} | {r.description[:200]}")
    return "\n".join(lines)


def correlate(
    config: Config,
    query: str,
    results: list[SearchResult],
    client=None,
    meter: CostMeter | None = None,
) -> dict:
    if not results:
        return {**_EMPTY, "summary": "No results to correlate."}

    results = results[: config.max_correlate]

    if client is None:
        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key)

    user = f"Query: {query}\n\nResults:\n{_compact(results)}"
    resp = client.chat.completions.create(
        model=config.chat_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    if meter is not None:
        usage = getattr(resp, "usage", None)
        if usage:
            meter.add(
                "correlation",
                config.chat_model,
                getattr(usage, "prompt_tokens", 0),
                getattr(usage, "completion_tokens", 0),
            )
    try:
        return json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError, IndexError):
        return {**_EMPTY, "summary": "Correlation returned unparseable output."}
