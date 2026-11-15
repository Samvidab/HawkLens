"""Unit tests for the Matterport client: auth, retries/backoff, 429, pagination,
GraphQL-error detection, and secret redaction. No network — httpx MockTransport only.
"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.matterport.client import (
    MatterportAuthError,
    MatterportClient,
    MatterportError,
)


def _settings(**over) -> Settings:
    base = dict(
        mp_token_id="tid-1234",
        mp_token_secret="sekret",
        cache_mode="off",  # exercise the transport on every call
        mp_max_retries=3,
        mp_backoff_base_s=0.0,  # no real sleeping in tests
    )
    base.update(over)
    return Settings(**base)


def _client(handler, **over) -> MatterportClient:
    return MatterportClient(_settings(**over), transport=httpx.MockTransport(handler))


async def test_missing_credentials_raises():
    with pytest.raises(MatterportAuthError):
        MatterportClient(Settings(mp_token_id=None, mp_token_secret=None))


async def test_repr_redacts_secret():
    c = _client(lambda req: httpx.Response(200, json={"data": {}}))
    text = repr(c)
    assert "sekret" not in text
    assert "***" in text
    await c.aclose()


async def test_basic_auth_header_sent():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"data": {"ok": True}})

    async with _client(handler) as c:
        data = await c.graphql("query { ok }", op_name="t")
    assert data == {"ok": True}
    # base64("tid-1234:sekret")
    assert seen["auth"].startswith("Basic ")


async def test_graphql_errors_raise():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": "nope"}]})

    async with _client(handler) as c:
        with pytest.raises(MatterportError):
            await c.graphql("query { x }", op_name="t")


async def test_auth_failure_raises_auth_error():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    async with _client(handler) as c:
        with pytest.raises(MatterportAuthError):
            await c.graphql("query { x }", op_name="t")


async def test_retries_then_succeeds():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"data": {"ok": 1}})

    async with _client(handler) as c:
        data = await c.graphql("query { ok }", op_name="t")
    assert data == {"ok": 1}
    assert calls["n"] == 3


async def test_retries_exhausted_raises():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with _client(handler, mp_max_retries=2) as c:
        with pytest.raises(MatterportError):
            await c.graphql("query { x }", op_name="t")


async def test_honor_retry_after_numeric():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")
        return httpx.Response(200, json={"data": {"ok": 1}})

    async with _client(handler) as c:
        data = await c.graphql("query { ok }", op_name="t")
    assert data == {"ok": 1}
    assert calls["n"] == 2


async def test_paginate_follows_string_cursor():
    # offset is a STRING cursor; first page sends no offset, then the server's nextOffset.
    pages = {
        None: {"results": [{"id": "a"}, {"id": "b"}], "totalResults": 3, "nextOffset": "cur2"},
        "cur2": {"results": [{"id": "c"}], "totalResults": 3, "nextOffset": None},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(req.content)
        offset = body["variables"].get("offset")
        return httpx.Response(200, json={"data": {"models": pages[offset]}})

    collected: list[str] = []
    async with _client(handler) as c:
        async for page in c.paginate(
            "query($offset:String,$pageSize:Int){ models(offset:$offset,pageSize:$pageSize) { results { id } totalResults nextOffset } }",
            connection_path=["models"],
            op_name="models",
            page_size=2,
        ):
            collected += [r["id"] for r in page]
    assert collected == ["a", "b", "c"]
