from pydantic import BaseModel

from app.agents import llm


class Toy(BaseModel):
    x: int


class Err(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


async def test_429_is_waited_out_using_retry_delay(monkeypatch):
    waits, calls = [], []

    async def fake_generate(model, prompt, images, schema):
        calls.append(1)
        if len(calls) < 3:
            raise Err(429, "RESOURCE_EXHAUSTED ... 'retryDelay': '8s'")
        return '{"x": 1}', 10

    async def fake_sleep(s):
        waits.append(s)

    monkeypatch.setattr(llm, "_generate", fake_generate)
    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
    assert await llm._call_with_retries("m", "p", [], Toy) == '{"x": 1}'
    assert waits == [9.0, 9.0] and len(calls) == 3


async def test_other_4xx_not_retried(monkeypatch):
    calls = []

    async def fake_generate(model, prompt, images, schema):
        calls.append(1)
        raise Err(404, "model not found")

    monkeypatch.setattr(llm, "_generate", fake_generate)
    try:
        await llm._call_with_retries("m", "p", [], Toy)
    except Err:
        pass
    assert len(calls) == 1


async def test_daily_quota_fails_fast(monkeypatch):
    calls = []

    async def fake_generate(model, prompt, images, schema):
        calls.append(1)
        raise Err(429, "PerDay quota ... 'retryDelay': '4440s'")

    monkeypatch.setattr(llm, "_generate", fake_generate)
    import pytest
    with pytest.raises(llm.QuotaExhausted):
        await llm._call_with_retries("m", "p", [], Toy)
    assert len(calls) == 1
