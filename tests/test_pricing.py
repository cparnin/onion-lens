from onionlens.pricing import CostMeter, cost


def test_cost_known_model():
    # 1M input tokens of gpt-4o-mini = $0.15
    assert round(cost("gpt-4o-mini", 1_000_000, 0), 2) == 0.15


def test_cost_unknown_model_is_zero():
    assert cost("mystery-model", 1000) == 0.0


def test_meter_totals():
    m = CostMeter()
    m.add("embeddings", "text-embedding-3-small", 1_000_000)
    m.add("correlation", "gpt-4o-mini", 1_000_000, 1_000_000)
    # 0.02 + 0.15 + 0.60
    assert round(m.total, 2) == 0.77
    assert "$" in m.summary()


def test_meter_empty():
    assert CostMeter().summary() == "no billable API calls this run"
