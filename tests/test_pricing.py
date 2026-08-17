from onionlens.pricing import CostMeter, cost


def test_cost_known_model():
    # 1M input tokens of claude-haiku-4-5 = $1.00
    assert round(cost("claude-haiku-4-5", 1_000_000, 0), 2) == 1.00


def test_cost_unknown_model_is_zero():
    assert cost("mystery-model", 1000) == 0.0


def test_meter_totals():
    m = CostMeter()
    m.add("correlation", "claude-haiku-4-5", 1_000_000, 1_000_000)
    # 1.00 input + 5.00 output
    assert round(m.total, 2) == 6.00
    assert "$" in m.summary()


def test_meter_empty():
    assert CostMeter().summary() == "no billable API calls this run"
