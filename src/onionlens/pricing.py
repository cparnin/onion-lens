"""Cost estimation.

Prices are USD per 1M tokens and are estimates. Update this table if Anthropic
changes pricing. The CostMeter accumulates real token usage returned by the API
so every run can report what it actually cost.
"""

PRICES = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
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
