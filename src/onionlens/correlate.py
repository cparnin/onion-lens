"""AI correlation layer.

Takes the raw result list and asks the model to do what the existing engines
cannot: cluster by theme, pull out shared entities, flag likely mirror or scam
duplicates, and suggest follow-up searches. Returns structured JSON.

Uses the Anthropic API with structured outputs, so the response is guaranteed
to match the schema below. Input is capped at config.max_correlate and
descriptions are truncated, so the per-run token cost stays bounded no matter
how many results were fetched.
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
  keys, and probable scams or phishing clones."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "addresses": {"type": "array", "items": {"type": "string"}},
                    "note": {"type": "string"},
                },
                "required": ["theme", "addresses", "note"],
                "additionalProperties": False,
            },
        },
        "entities": {
            "type": "object",
            "properties": {
                "handles": {"type": "array", "items": {"type": "string"}},
                "wallets": {"type": "array", "items": {"type": "string"}},
                "emails": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["handles", "wallets", "emails"],
            "additionalProperties": False,
        },
        "likely_duplicates_or_scams": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "addresses": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["addresses", "reason"],
                "additionalProperties": False,
            },
        },
        "suggested_followups": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "clusters",
        "entities",
        "likely_duplicates_or_scams",
        "suggested_followups",
    ],
    "additionalProperties": False,
}

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
        from anthropic import Anthropic

        client = Anthropic(api_key=config.anthropic_api_key)

    user = f"Query: {query}\n\nResults:\n{_compact(results)}"
    resp = client.messages.create(
        model=config.chat_model,
        max_tokens=4096,
        system=_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[{"role": "user", "content": user}],
    )
    if meter is not None:
        usage = getattr(resp, "usage", None)
        if usage:
            meter.add(
                "correlation",
                config.chat_model,
                getattr(usage, "input_tokens", 0),
                getattr(usage, "output_tokens", 0),
            )
    if getattr(resp, "stop_reason", None) == "refusal":
        return {**_EMPTY, "summary": "Correlation declined by the model's safety policy."}
    try:
        text = next(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return json.loads(text)
    except (json.JSONDecodeError, AttributeError, StopIteration):
        return {**_EMPTY, "summary": "Correlation returned unparseable output."}
