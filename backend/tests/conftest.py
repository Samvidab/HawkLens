import pytest


@pytest.fixture(autouse=True)
def composer_llm_off(monkeypatch):
    """Tests never call Gemini from the composer; tests that want an LLM answer patch it explicitly."""
    from app.agents import composer

    async def _off(prompt, schema, **kw):
        raise RuntimeError("composer LLM disabled in tests")

    monkeypatch.setattr(composer, "text_json", _off)
