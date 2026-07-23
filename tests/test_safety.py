from onionlens.safety import is_allowed


def test_allows_normal_query():
    allowed, reason = is_allowed("ransomware leak sites")
    assert allowed is True
    assert reason == ""


def test_blocks_abuse_category():
    for bad in ["csam", "child porn", "underage content", "p e d o"]:
        allowed, reason = is_allowed(bad)
        assert allowed is False
        assert "abuse" in reason


def test_handles_empty():
    allowed, _ = is_allowed("")
    assert allowed is True
