import pytest
from PIL import Image
from pydantic import BaseModel

from app.agents import llm
from app.config import get_settings


class Toy(BaseModel):
    color: str
    count: int


class Img:
    def __init__(self, image_id, path):
        self.image_id, self.local_path = image_id, str(path)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_VISION", "vis-model")
    monkeypatch.setenv("GEMINI_MODEL_FAST", "fast-model")
    monkeypatch.setenv("CACHE_MODE", "read_write")
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("MAX_TOKENS_PER_SURVEY", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "BACKOFF_S", 0)
    monkeypatch.setattr(llm, "tokens_used", 0)
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def image(env):
    p = env / "big.png"
    Image.new("RGB", (4000, 2000), "red").save(p)
    return Img("img1", p)


def fake_generate(replies, calls):
    async def _g(model, prompt, images, schema):
        calls.append((model, prompt, images))
        r = replies[min(len(calls) - 1, len(replies) - 1)]
        if isinstance(r, Exception):
            raise r
        return r, 10
    return _g


async def test_vision_valid_and_cached(env, image, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_generate", fake_generate(['{"color":"red","count":3}'], calls))
    a = await llm.vision_json("what?", [image], Toy)
    b = await llm.vision_json("what?", [image], Toy)
    assert a == b == Toy(color="red", count=3)
    assert len(calls) == 1  # second call served from cache
    assert calls[0][0] == "vis-model"
    assert llm.tokens_used == 10


async def test_cache_read_only_no_network(env, image, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_generate", fake_generate(['{"color":"red","count":3}'], calls))
    await llm.vision_json("q", [image], Toy)
    monkeypatch.setenv("CACHE_MODE", "read_only")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_generate", fake_generate([RuntimeError("no network")], []))
    assert (await llm.vision_json("q", [image], Toy)).count == 3
    from app.adapters.cache import CacheMiss
    with pytest.raises(CacheMiss):
        await llm.vision_json("other prompt", [image], Toy)


async def test_image_downscaled(env, image, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_generate", fake_generate(['{"color":"r","count":1}'], calls))
    await llm.vision_json("q", [image], Toy)
    import io
    im = Image.open(io.BytesIO(calls[0][2][0]))
    assert max(im.size) == llm.MAX_IMAGE_SIDE


async def test_transport_retry(env, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_generate", fake_generate(
        [RuntimeError("503"), RuntimeError("503"), '{"color":"b","count":2}'], calls))
    assert (await llm.text_json("q", Toy)).color == "b"
    assert len(calls) == 3 and calls[0][0] == "fast-model"


async def test_transport_gives_up(env, monkeypatch):
    monkeypatch.setattr(llm, "_generate", fake_generate([RuntimeError("down")], []))
    with pytest.raises(RuntimeError, match="down"):
        await llm.text_json("q", Toy)


async def test_validation_retry_includes_error(env, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "_generate", fake_generate(
        ['{"color":"r","count":"many"}', '{"color":"r","count":4}'], calls))
    assert (await llm.text_json("q", Toy)).count == 4
    assert "count" in calls[1][1] and "invalid" in calls[1][1]


async def test_validation_fails_twice_raises(env, monkeypatch):
    from pydantic import ValidationError
    monkeypatch.setattr(llm, "_generate", fake_generate(['{"bad":1}'], []))
    with pytest.raises(ValidationError):
        await llm.text_json("q", Toy)


async def test_token_budget(env, monkeypatch):
    monkeypatch.setenv("MAX_TOKENS_PER_SURVEY", "5")
    monkeypatch.setattr(llm, "tokens_used", 5)
    with pytest.raises(llm.TokenBudgetExceeded):
        await llm.text_json("q", Toy)


async def test_hung_call_times_out_and_retries(env, monkeypatch):
    monkeypatch.setattr(llm, "CALL_TIMEOUT_S", 0.05)
    n = {"c": 0}

    async def slow_then_ok(model, prompt, images, schema):
        n["c"] += 1
        if n["c"] == 1:
            await asyncio.sleep(5)
        return '{"color":"g","count":1}', 1

    import asyncio
    monkeypatch.setattr(llm, "_generate", slow_then_ok)
    assert (await llm.text_json("q", Toy)).color == "g" and n["c"] == 2


async def test_client_error_is_not_retried(env, monkeypatch):
    class NotFound(Exception):
        code = 404

    calls = []
    monkeypatch.setattr(llm, "_generate", fake_generate([NotFound("no such model")], calls))
    with pytest.raises(NotFound):
        await llm.text_json("q", Toy)
    assert len(calls) == 1


def model_replies(by_model, calls):
    async def _g(model, prompt, images, schema):
        calls.append(model)
        r = by_model[model]
        if isinstance(r, Exception):
            raise r
        return r, 5
    return _g


class ServerErr(Exception):
    code = 503


async def test_vision_falls_back_on_5xx_and_caches_under_primary(env, image, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_VISION_FALLBACK", "fb-model")
    calls = []
    monkeypatch.setattr(llm, "_generate", model_replies({"vis-model": ServerErr("busy"), "fb-model": '{"color":"x","count":1}'}, calls))
    assert (await llm.vision_json("q", [image], Toy)).color == "x"
    assert calls == ["vis-model"] * 3 + ["fb-model"]  # primary retries, then one fallback call
    calls.clear()
    assert (await llm.vision_json("q", [image], Toy)).color == "x" and calls == []  # cached


async def test_vision_falls_back_on_timeout(env, image, monkeypatch):
    import asyncio
    monkeypatch.setenv("GEMINI_MODEL_VISION_FALLBACK", "fb-model")
    monkeypatch.setattr(llm, "RETRIES", 0)
    calls = []
    monkeypatch.setattr(llm, "_generate", model_replies({"vis-model": asyncio.TimeoutError(), "fb-model": '{"color":"t","count":2}'}, calls))
    assert (await llm.vision_json("q", [image], Toy)).count == 2
    assert calls == ["vis-model", "fb-model"]


async def test_vision_no_fallback_on_4xx_or_when_unset(env, image, monkeypatch):
    class NF(Exception):
        code = 404
    monkeypatch.setenv("GEMINI_MODEL_VISION_FALLBACK", "fb-model")
    calls = []
    monkeypatch.setattr(llm, "_generate", model_replies({"vis-model": NF("x"), "fb-model": '{"color":"x","count":1}'}, calls))
    with pytest.raises(NF):
        await llm.vision_json("q", [image], Toy)
    assert calls == ["vis-model"]
    monkeypatch.delenv("GEMINI_MODEL_VISION_FALLBACK")
    monkeypatch.setattr(llm, "_env", lambda n: None)
    calls.clear()
    monkeypatch.setattr(llm, "_generate", model_replies({"vis-model": ServerErr("busy")}, calls))
    with pytest.raises(ServerErr):
        await llm.vision_json("q2", [image], Toy)
    assert "fb-model" not in calls


async def test_text_json_never_uses_vision_fallback(env, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_VISION_FALLBACK", "fb-model")
    calls = []
    monkeypatch.setattr(llm, "_generate", model_replies({"fast-model": ServerErr("busy")}, calls))
    with pytest.raises(ServerErr):
        await llm.text_json("q", Toy)
    assert set(calls) == {"fast-model"}
