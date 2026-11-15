import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from app import events
from app.config import get_settings


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    events._seq.clear(); events._subs.clear()
    a = FastAPI()
    a.include_router(events.router)
    yield a
    get_settings.cache_clear()


def test_emit_appends_jsonl_with_seq(app, tmp_path):
    e0 = events.emit("r1", "Records", "fetch", "36 stories", building_id="b1", evidence_id="i1")
    e1 = events.emit("r1", "Aerial", "observe", "x" * 200, building_name="Allen Center")
    assert (e0.seq, e1.seq) == (0, 1)
    assert len(e1.message) == events.MAX_MESSAGE
    lines = (tmp_path / "runs/r1/events.jsonl").read_text().splitlines()
    assert [json.loads(l)["seq"] for l in lines] == [0, 1]
    assert json.loads(lines[0])["evidence_id"] == "i1"
    # numbering continues after a restart
    events._seq.clear()
    assert events.emit("r1", "A", "plan", "m").seq == 2


async def _collect(app, url):
    out = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        async with c.stream("GET", url) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            async for line in r.aiter_lines():
                if line.startswith("data:"):
                    out.append(json.loads(line[5:]))
    return out


async def test_sse_live_gets_past_and_new_events(app):
    events.emit("r2", "Orchestrator", "plan", "past event")

    async def producer():
        await asyncio.sleep(0.2)
        events.emit("r2", "Aerial", "observe", "live event")
        events.emit("r2", "Orchestrator", "done", "finished")

    got, _ = await asyncio.wait_for(asyncio.gather(_collect(app, "/events/r2"), producer()), 10)
    assert [e["message"] for e in got] == ["past event", "live event", "finished"]
    assert [e["seq"] for e in got] == [0, 1, 2]


async def test_sse_replay_from_file(app):
    events.emit("r3", "A", "plan", "one")
    events.emit("r3", "A", "send_back", "two")
    events.emit("r3", "A", "done", "three")
    events._seq.clear(); events._subs.clear()  # new process, file only
    got = await asyncio.wait_for(_collect(app, "/events/r3?replay=1&delay=0"), 10)
    assert [e["message"] for e in got] == ["one", "two", "three"]
