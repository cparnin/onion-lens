"""Shared test fixtures, including a fake OpenAI client so store and correlation
logic can be tested without network access or an API key."""

import pytest


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeEmbeddings:
    def __init__(self, dims=8):
        self.dims = dims

    def create(self, model, input):
        # deterministic pseudo-embedding based on text length
        data = [_Obj(embedding=[float((len(t) + i) % 7) for i in range(self.dims)]) for t in input]
        return _Obj(data=data, usage=_Obj(total_tokens=sum(len(t) for t in input)))


class FakeChat:
    def __init__(self, payload):
        self._payload = payload

    def create(self, model, response_format, messages):
        msg = _Obj(content=self._payload)
        return _Obj(choices=[_Obj(message=msg)], usage=_Obj(prompt_tokens=100, completion_tokens=50))


class FakeClient:
    def __init__(self, chat_payload='{"summary": "ok"}'):
        self.embeddings = FakeEmbeddings()
        self.chat = _Obj(completions=FakeChat(chat_payload))


@pytest.fixture
def fake_client():
    return FakeClient()
