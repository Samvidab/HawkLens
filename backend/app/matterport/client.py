"""Typed Matterport GraphQL client.

Auth: HTTP basic (token id = username, secret = password), read from settings.
The secret is never logged and is redacted in repr.

Reliability: retries on 429/5xx/network with exponential backoff + jitter, honoring
Retry-After. Retries happen *inside* the cached function, so only a final success is
stored. Every call goes through app.adapters.cache.cached, keyed by operation name +
variables, so the same query replays identically offline (CACHE_MODE=read_only).

The exact GraphQL query strings and the Model field list are NOT defined here; they
are written after schema introspection (see schema.py and task 1.5) so we never guess.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any, AsyncIterator

import httpx

from app.adapters.cache import cached
from app.config import Settings, get_settings

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class MatterportError(RuntimeError):
    """A Matterport request failed (transport, non-2xx after retries, or GraphQL errors)."""


class MatterportAuthError(MatterportError):
    """Credentials are missing or rejected."""


class MatterportClient:
    """Async GraphQL client for the Matterport Model API."""

    def __init__(self, settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None):
        self._s = settings or get_settings()
        if not self._s.mp_token_id or not self._s.mp_token_secret:
            raise MatterportAuthError(
                "MP_TOKEN_ID and MP_TOKEN_SECRET must be set (see backend/.env.example)."
            )
        self._client = httpx.AsyncClient(
            base_url="",
            auth=httpx.BasicAuth(self._s.mp_token_id, self._s.mp_token_secret),
            timeout=httpx.Timeout(30.0),
            transport=transport,
        )

    def __repr__(self) -> str:  # never leak the secret
        tid = self._s.mp_token_id or ""
        shown = f"{tid[:4]}…" if tid else "unset"
        return f"MatterportClient(token_id={shown}, secret=***, url={self._s.mp_api_url})"

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "MatterportClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # -- core -------------------------------------------------------------

    async def graphql(self, query: str, variables: dict[str, Any] | None = None, *, op_name: str) -> dict[str, Any]:
        """Run a GraphQL operation and return its `data` object.

        Cached by (op_name, variables). Raises MatterportError on failure.
        """
        variables = variables or {}

        async def _do() -> dict[str, Any]:
            payload = {"query": query, "variables": variables}
            resp = await self._request_with_retries(payload)
            body = resp.json()
            if body.get("errors"):
                raise MatterportError(f"GraphQL errors for {op_name}: {body['errors']}")
            if "data" not in body:
                raise MatterportError(f"No data in response for {op_name}: {body}")
            return body["data"]

        # Use this client's settings for the cache mode/root so a client built with an
        # explicit Settings (e.g. in tests) is not overridden by the global get_settings().
        return await cached(
            "matterport",
            {"op": op_name, "variables": variables},
            _do,
            mode=self._s.cache_mode,
            root=self._s.cache_dir,
        )

    async def _request_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._s.mp_max_retries + 1):
            try:
                resp = await self._client.post(self._s.mp_api_url, json=payload)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                await self._sleep_before_retry(attempt, None)
                continue

            if resp.status_code == 401 or resp.status_code == 403:
                raise MatterportAuthError(f"Matterport rejected credentials (HTTP {resp.status_code}).")
            if resp.status_code in _RETRYABLE_STATUS and attempt < self._s.mp_max_retries:
                await self._sleep_before_retry(attempt, resp.headers.get("Retry-After"))
                continue
            if resp.status_code >= 400:
                raise MatterportError(f"Matterport HTTP {resp.status_code}: {resp.text[:500]}")
            return resp

        raise MatterportError(f"Exhausted retries ({self._s.mp_max_retries}); last error: {last_exc}")

    async def _sleep_before_retry(self, attempt: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                await asyncio.sleep(float(retry_after))
                return
            except ValueError:
                pass  # non-numeric Retry-After (HTTP date) — fall through to backoff
        delay = self._s.mp_backoff_base_s * (2**attempt) + random.uniform(0, self._s.mp_backoff_base_s)
        await asyncio.sleep(delay)

    # -- pagination -------------------------------------------------------

    async def paginate(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        connection_path: list[str],
        op_name: str,
        page_size: int = 100,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Yield pages of `results` by following nextOffset until totalResults is reached.

        Matterport's `offset` is a STRING cursor: the first page sends no offset, and
        each subsequent page passes the server's returned `nextOffset` string verbatim.
        `connection_path` is the key path from `data` to the connection object holding
        `results`, `totalResults`, and `nextOffset` (e.g. ["models"]).
        """
        variables = dict(variables or {})
        offset: str | None = None
        seen = 0
        page_no = 0
        while True:
            vars_this = dict(variables)
            vars_this["pageSize"] = page_size
            if offset is not None:
                vars_this["offset"] = offset
            data = await self.graphql(query, vars_this, op_name=f"{op_name}@{page_no}")
            conn = data
            for key in connection_path:
                conn = conn[key]
            results = conn.get("results", [])
            total = conn.get("totalResults", len(results))
            next_offset = conn.get("nextOffset")
            if results:
                yield results
                seen += len(results)
            if not next_offset or not results or seen >= total:
                break
            offset = next_offset
            page_no += 1
