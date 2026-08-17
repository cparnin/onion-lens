"""Shared test fixtures, including a fake Anthropic client so correlation logic
can be tested without network access or an API key."""

import pytest


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeMessages:
    def __init__(self, payload):
        self._payload = payload

    def create(self, model, max_tokens, system, output_config, messages):
        block = _Obj(type="text", text=self._payload)
        return _Obj(
            content=[block],
            stop_reason="end_turn",
            usage=_Obj(input_tokens=100, output_tokens=50),
        )


class FakeClient:
    def __init__(self, payload='{"summary": "ok"}'):
        self.messages = FakeMessages(payload)


@pytest.fixture
def fake_client():
    return FakeClient()
