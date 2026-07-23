"""Cost estimation.

Prices are USD per 1M tokens and are estimates. Update this table if OpenAI
changes pricing. The CostMeter accumulates real token usage returned by the API
so every run can report what it actually cost.
"""

PRICES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
}


def cost(model: str, input_tokens: int, output_tokens: int = 0) -> float:
    p = PRICES.get(model)
    if not p:
        return 0.0
    return input_tokens / 1e6 * p["input"] + output_tokens / 1e6 * p["output"]


class CostMeter:
    """Accumulates token usage and dollar cost across a single run."""

    def __init__(self):
        self.items: list[tuple[str, str, int, int, float]] = []

    def add(self, label: str, model: str, input_tokens: int, output_tokens: int = 0) -> None:
        usd = cost(model, input_tokens, output_tokens)
        self.items.append((label, model, input_tokens, output_tokens, usd))

    @property
    def total(self) -> float:
        return sum(item[4] for item in self.items)

    def summary(self) -> str:
        if not self.items:
            return "no billable API calls this run"
        parts = [f"{label} {in_t + out_t} tok" for label, _, in_t, out_t, _ in self.items]
        return f"{', '.join(parts)}  =>  ${self.total:.4f}"
