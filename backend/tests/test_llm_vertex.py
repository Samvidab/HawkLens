import types as pytypes

import pytest
from pydantic import BaseModel

from app.agents import llm
from app.config import get_settings


class Toy(BaseModel):
    x: int


def fake_env(monkeypatch, **vals):
    monkeypatch.setattr(llm, "env_value", lambda name: vals.get(name))


@pytest.mark.parametrize("v,expected", [("true", True), ("TRUE", True), ("1", True), ("yes", True), (" true ", True),
                                        ("false", False), ("0", False), ("", False), (None, False)])
def test_use_vertex_flag(monkeypatch, v, expected):
    fake_env(monkeypatch, GOOGLE_GENAI_USE_VERTEXAI=v)
    assert llm.use_vertex() is expected


@pytest.fixture
def recorder(monkeypatch):
    calls = []
    import google.genai as genai
    monkeypatch.setattr(genai, "Client", lambda **kw: calls.append(kw) or object())
    return calls


def test_vertex_client_uses_the_vertex_api_key_first(monkeypatch, recorder):
    fake_env(monkeypatch, GOOGLE_GENAI_USE_VERTEXAI="true", VERTEX_API_KEY="v-key", GOOGLE_CLOUD_PROJECT="my-proj",
             GOOGLE_CLOUD_LOCATION="global", GEMINI_API_KEY="studio-key")
    llm.make_client()
    # exactly vertexai + api_key: the SDK rejects an api_key combined with project/location, and the AI Studio key is not used
    assert recorder == [{"vertexai": True, "api_key": "v-key"}]


def test_vertex_without_an_api_key_falls_back_to_adc(monkeypatch, recorder):
    fake_env(monkeypatch, GOOGLE_GENAI_USE_VERTEXAI="true", GOOGLE_CLOUD_PROJECT="my-proj", GOOGLE_CLOUD_LOCATION="global",
             GEMINI_API_KEY="should-not-be-used")
    llm.make_client()
    assert recorder == [{"vertexai": True, "project": "my-proj", "location": "global"}]  # no api_key: Application Default Credentials


@pytest.mark.parametrize("missing", ["GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"])
def test_vertex_needs_an_api_key_or_project_and_location(monkeypatch, recorder, missing):
    vals = {"GOOGLE_GENAI_USE_VERTEXAI": "true", "GOOGLE_CLOUD_PROJECT": "p", "GOOGLE_CLOUD_LOCATION": "global"}
    vals.pop(missing)
    fake_env(monkeypatch, **vals)
    with pytest.raises(RuntimeError, match="VERTEX_API_KEY, or GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION"):
        llm.make_client()
    assert recorder == []


def test_api_key_client_when_vertex_is_off(monkeypatch, recorder):
    fake_env(monkeypatch, GOOGLE_GENAI_USE_VERTEXAI="false", VERTEX_API_KEY="v-key", GOOGLE_CLOUD_PROJECT="p",
             GOOGLE_CLOUD_LOCATION="global")  # flag off: the old api_key client, whatever Vertex settings exist
    monkeypatch.setenv("GEMINI_API_KEY", "k-123"); get_settings.cache_clear()
    llm.make_client()
    assert recorder == [{"api_key": "k-123"}]
    monkeypatch.delenv("GEMINI_API_KEY"); monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        llm.make_client()
    get_settings.cache_clear()


async def test_generate_calls_the_selected_client(monkeypatch):
    seen = {}

    class Models:
        async def generate_content(self, model, contents, config):
            seen.update(model=model, n_parts=len(contents), schema=config.response_schema)
            return pytypes.SimpleNamespace(text='{"x": 1}', usage_metadata=pytypes.SimpleNamespace(total_token_count=42))

    client = pytypes.SimpleNamespace(aio=pytypes.SimpleNamespace(models=Models()))
    monkeypatch.setattr(llm, "make_client", lambda: client)
    assert await llm._generate("gemini-x", "prompt", [], Toy) == ('{"x": 1}', 42)
    assert seen == {"model": "gemini-x", "n_parts": 1, "schema": Toy}


class Err(Exception):
    def __init__(self, code, msg=""):
        super().__init__(msg or f"HTTP {code}")
        self.code = code


async def test_402_is_out_of_credit_and_fails_fast(monkeypatch):
    calls, slept = [], []

    async def gen(model, prompt, images, schema):
        calls.append(model)
        raise Err(402, "402 Payment Required")

    async def sleep(s): slept.append(s)
    monkeypatch.setattr(llm, "_generate", gen); monkeypatch.setattr(llm.asyncio, "sleep", sleep)
    fake_env(monkeypatch, GOOGLE_GENAI_USE_VERTEXAI="false")
    with pytest.raises(llm.OutOfCredit) as e:
        await llm._call_with_retries("m", "p", [], Toy)
    assert calls == ["m"] and slept == []  # one attempt, no retries, no waiting
    assert "402" in str(e.value) and "GOOGLE_GENAI_USE_VERTEXAI" in str(e.value)
    assert isinstance(e.value, llm.QuotaExhausted) and isinstance(e.value.__cause__, Err)
    fake_env(monkeypatch, GOOGLE_GENAI_USE_VERTEXAI="true")
    with pytest.raises(llm.OutOfCredit, match="Google Cloud account"):
        await llm._call_with_retries("m", "p", [], Toy)


async def test_402_does_not_trigger_the_vision_fallback(monkeypatch, tmp_path):
    calls = []

    async def gen(model, prompt, images, schema):
        calls.append(model); raise Err(402)

    monkeypatch.setattr(llm, "_generate", gen)
    monkeypatch.setenv("GEMINI_MODEL_VISION", "vis"); monkeypatch.setenv("CACHE_DIR", str(tmp_path)); monkeypatch.setenv("CACHE_MODE", "read_write")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_env", lambda n: "fallback-model" if n == "GEMINI_MODEL_VISION_FALLBACK" else None)
    from PIL import Image
    img = tmp_path / "i.png"; Image.new("RGB", (8, 8)).save(img)
    ref = pytypes.SimpleNamespace(image_id="i", local_path=str(img))
    with pytest.raises(llm.OutOfCredit):
        await llm.vision_json("q", [ref], Toy)
    assert calls == ["vis"]  # the fallback model is not tried: it would be billed the same way
    get_settings.cache_clear()
