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
from app.config import get_settings
from app.envutil import env_value

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

MAX_IMAGE_SIDE = 1536
CALL_TIMEOUT_S = 60.0  # per Gemini request; a hung call counts as a failed attempt
RETRIES = 2  # transport retries after the first attempt
BACKOFF_S = 1.0
RATE_LIMIT_RETRIES = 8  # 429s are waited out (free-tier keys: a few requests per minute)
RATE_LIMIT_DEFAULT_WAIT_S = 15.0
RATE_LIMIT_MAX_WAIT_S = 90.0  # longer asks mean a daily quota is spent: fail fast instead of hanging
CACHE_NAMESPACE = "gemini"

_sem: asyncio.Semaphore | None = None
_sem_loop: asyncio.AbstractEventLoop | None = None
tokens_used: int = 0  # running total; callers may reset between surveys


class TokenBudgetExceeded(RuntimeError):
    pass


class QuotaExhausted(RuntimeError):
    """The API asked for a wait longer than RATE_LIMIT_MAX_WAIT_S (daily quota spent)."""


class OutOfCredit(QuotaExhausted):
    """HTTP 402: the prepaid balance is spent. Fail fast (no retry, no fallback model); top up or use Vertex AI."""


class ImageLike(Protocol):  # adapters.vexcel.ImageRef satisfies this
    image_id: str
    local_path: str


_env = env_value  # name kept: tests and finance.py patch/import llm._env


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


_pace_lock: asyncio.Lock | None = None
_pace_loop: asyncio.AbstractEventLoop | None = None
_last_start = 0.0


def _rpm() -> float:
    """GEMINI_RPM from the environment: max request starts per minute (0 = no pacing)."""
    try:
        return float(os.environ.get("GEMINI_RPM", "0"))
    except ValueError:
        return 0.0


async def _pace() -> None:
    global _pace_lock, _pace_loop, _last_start
    rpm = _rpm()
    if rpm <= 0:
        return
    loop = asyncio.get_running_loop()
    if _pace_lock is None or _pace_loop is not loop:
        _pace_lock, _pace_loop = asyncio.Lock(), loop
    async with _pace_lock:
        wait = _last_start + 60.0 / rpm - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_start = loop.time()


def _retry_delay_s(e: Exception) -> float:
    """Seconds the API asks us to wait on a 429 (RetryInfo.retryDelay), else a default."""
    import re
    m = re.search(r"retry(?:Delay)?['\"]?\s*[:in]+\s*['\"]?(\d+(?:\.\d+)?)s", str(e))
    return (float(m.group(1)) + 1.0) if m else RATE_LIMIT_DEFAULT_WAIT_S


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


def use_vertex() -> bool:
    """GOOGLE_GENAI_USE_VERTEXAI=true: call Gemini through Vertex AI (billed to the Google Cloud project)."""
    return (env_value("GOOGLE_GENAI_USE_VERTEXAI") or "").strip().lower() in ("1", "true", "yes")


def make_client():
    """Vertex AI with Application Default Credentials when GOOGLE_GENAI_USE_VERTEXAI is true, else the AI Studio
    api-key client. The Google SDK reads these variables only from the process environment, so they are read here
    (process env, then backend/.env) and passed explicitly."""
    from google import genai

    if use_vertex():
        project, location = env_value("GOOGLE_CLOUD_PROJECT"), env_value("GOOGLE_CLOUD_LOCATION")
        if not project or not location:
            raise RuntimeError("Vertex AI needs GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION")
        return genai.Client(vertexai=True, project=project, location=location)
    key = get_settings().gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=key)


async def _generate(model: str, prompt: str, images: list[bytes], schema: type[BaseModel]) -> tuple[str, int]:
    """One Gemini call -> (json text, total tokens). Patched in tests."""
    from google.genai import types

    client = make_client()
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
    attempt = limited = 0
    while True:
        try:
            async with _semaphore():
                await _pace()
                text, tokens = await asyncio.wait_for(
                    _generate(model, prompt, images, schema), CALL_TIMEOUT_S)
            tokens_used += tokens
            log.info("gemini model=%s tokens=%d total=%d", model, tokens, tokens_used)
            return text
        except Exception as e:  # noqa: BLE001 - transport/API errors
            code = getattr(e, "code", None)
            if code == 402:  # prepaid credit exhausted: nothing to wait for
                raise OutOfCredit(
                    "Gemini is out of credit (HTTP 402): check billing on the Google Cloud project" if use_vertex() else
                    "Gemini API is out of credit (HTTP 402): top up the AI Studio balance, or set "
                    "GOOGLE_GENAI_USE_VERTEXAI=true to bill the Google Cloud project instead") from e
            if code == 429 and limited < RATE_LIMIT_RETRIES:  # rate limited: wait as told, don't count
                limited += 1
                delay = _retry_delay_s(e)
                if delay > RATE_LIMIT_MAX_WAIT_S:
                    raise QuotaExhausted(f"Gemini quota exhausted for {model}; API asks to wait {delay:.0f} s") from e
                log.warning("gemini 429; waiting %.0f s (%d/%d)", delay, limited, RATE_LIMIT_RETRIES)
                await asyncio.sleep(delay)
                continue
            if isinstance(code, int) and 400 <= code < 500 and code != 408:
                raise  # bad model name / key / request (or quota still exhausted): retrying cannot help
            if attempt >= RETRIES:
                raise
            await asyncio.sleep(BACKOFF_S * 2**attempt)
            attempt += 1


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
