"""Gemini wrapper: structured JSON output validated by Pydantic, cached, rate-limited.

LLMs describe and decide; they never produce numbers shown to users (see guardrails.py).
Every call goes through adapters.cache so the demo runs with CACHE_MODE=read_only.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Any, Protocol, TypeVar

from PIL import Image
from pydantic import BaseModel, ValidationError

from app.adapters.cache import cached
from app.config import BACKEND_DIR, get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

MAX_IMAGE_SIDE = 1536
CALL_TIMEOUT_S = 60.0  # per Gemini request; a hung call counts as a failed attempt
RETRIES = 2  # transport retries after the first attempt
BACKOFF_S = 1.0
CACHE_NAMESPACE = "gemini"

_sem: asyncio.Semaphore | None = None
_sem_loop: asyncio.AbstractEventLoop | None = None
tokens_used: int = 0  # running total; callers may reset between surveys


class TokenBudgetExceeded(RuntimeError):
    pass


class ImageLike(Protocol):  # adapters.vexcel.ImageRef satisfies this
    image_id: str
    local_path: str


def _env(name: str) -> str | None:
    """Process env first, then backend/.env (Settings drops keys it does not declare)."""
    if os.environ.get(name):
        return os.environ[name]
    from dotenv import dotenv_values

    return dotenv_values(BACKEND_DIR / ".env").get(name) or None


def token_budget() -> int:
    """MAX_TOKENS_PER_SURVEY (0 = unlimited). config.py is outside this lane."""
    try:
        return int(_env("MAX_TOKENS_PER_SURVEY") or 0)
    except ValueError:
        return 0


def _should_fall_back(e: Exception) -> bool:
    """Server-side failure or timeout (after the primary model's retries)."""
    code = getattr(e, "code", None)
    return isinstance(e, (asyncio.TimeoutError, TimeoutError)) or (isinstance(code, int) and 500 <= code < 600)


def _semaphore() -> asyncio.Semaphore:
    global _sem, _sem_loop
    loop = asyncio.get_running_loop()
    if _sem is None or _sem_loop is not loop:
        _sem, _sem_loop = asyncio.Semaphore(get_settings().max_concurrent_buildings), loop
    return _sem


def downscale(path: str, max_side: int = MAX_IMAGE_SIDE) -> bytes:
    """JPEG bytes of the image with its longest side <= max_side."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=88)
        return buf.getvalue()


async def _generate(model: str, prompt: str, images: list[bytes], schema: type[BaseModel]) -> tuple[str, int]:
    """One Gemini call -> (json text, total tokens). Patched in tests."""
    from google import genai
    from google.genai import types

    key = get_settings().gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=key)
    parts: list[Any] = [types.Part.from_bytes(data=b, mime_type="image/jpeg") for b in images]
    parts.append(prompt)
    resp = await client.aio.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        ),
    )
    usage = getattr(resp, "usage_metadata", None)
    return resp.text or "", int(getattr(usage, "total_token_count", 0) or 0)


async def _call_with_retries(model: str, prompt: str, images: list[bytes], schema: type[BaseModel]) -> str:
    global tokens_used
    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            async with _semaphore():
                text, tokens = await asyncio.wait_for(
                    _generate(model, prompt, images, schema), CALL_TIMEOUT_S)
            tokens_used += tokens
            log.info("gemini model=%s tokens=%d total=%d", model, tokens, tokens_used)
            return text
        except Exception as e:  # noqa: BLE001 - transport/API errors
            last = e
            code = getattr(e, "code", None)
            if isinstance(code, int) and 400 <= code < 500 and code not in (408, 429):
                raise  # bad model name / key / request: retrying cannot help
            if attempt < RETRIES:
                await asyncio.sleep(BACKOFF_S * 2**attempt)
    assert last is not None
    raise last


async def _structured(model: str, prompt: str, images: list[ImageLike], schema: type[T],
                      fallback_model: str | None = None) -> T:
    budget = token_budget()
    if budget and tokens_used >= budget:
        raise TokenBudgetExceeded(f"{tokens_used} tokens used, budget {budget}")

    blobs = [downscale(i.local_path) for i in images]

    def params(p: str) -> dict:
        return {"model": model, "prompt": p, "image_ids": [i.image_id for i in images],
                "schema": schema.__name__, "schema_fields": sorted(schema.model_fields)}

    async def call(p: str) -> str:
        try:
            return await _call_with_retries(model, p, blobs, schema)
        except Exception as e:  # noqa: BLE001
            if not fallback_model or fallback_model == model or not _should_fall_back(e):
                raise
            log.warning("gemini %s failed (%s); falling back once to %s", model, type(e).__name__, fallback_model)
            return await _call_with_retries(fallback_model, p, blobs, schema)

    async def attempt(p: str) -> str:
        # Cached under the primary model's key whichever model answered, so read_only replays hit.
        return await cached(CACHE_NAMESPACE, params(p), lambda: call(p))

    text = await attempt(prompt)
    try:
        return schema.model_validate_json(text)
    except ValidationError as err:
        # Retry once with the validation error in the prompt (TRD §10), then give up to the caller,
        # which falls back to a template / `unknown` values.
        retry_prompt = (f"{prompt}\n\nYour previous reply was invalid JSON for the schema:\n{err}\n"
                        "Reply again with valid JSON only.")
        return schema.model_validate_json(await attempt(retry_prompt))


async def vision_json(prompt: str, images: list[ImageLike], schema: type[T]) -> T:
    """Strongest multimodal model (GEMINI_MODEL_VISION); one retry on GEMINI_MODEL_VISION_FALLBACK
    if it fails with a 5xx or timeout after its own retries."""
    model = get_settings().gemini_model_vision
    if not model:
        raise RuntimeError("GEMINI_MODEL_VISION is not set")
    return await _structured(model, prompt, images, schema, _env("GEMINI_MODEL_VISION_FALLBACK"))


async def text_json(prompt: str, schema: type[T], *, fast: bool = True) -> T:
    """Cheaper text model (GEMINI_MODEL_FAST) for composer/memo/orchestrator."""
    s = get_settings()
    model = s.gemini_model_fast if fast else s.gemini_model_vision
    if not model:
        raise RuntimeError("GEMINI_MODEL_FAST is not set")
    return await _structured(model, prompt, [], schema)
