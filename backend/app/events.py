"""Activity feed bus: emit() appends to runs/<run_id>/events.jsonl and fans out to live SSE clients.

Mount `router` in main.py (`app.include_router(events.router)`) to serve GET /events/{run_id}.
  ?replay=1  streams the saved events paced for the demo (no live subscription, works offline).
Live streams end after an event of kind "done" (or "error" is just an event; only "done" closes).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.schemas.events import ActivityEvent, EventKind

MAX_MESSAGE = 90
REPLAY_TOTAL_S = 35.0  # target length of a paced replay
REPLAY_MIN_DELAY_S, REPLAY_MAX_DELAY_S = 0.1, 2.5
DWELL = {"send_back": 2.5, "verify": 1.5, "plan": 1.5, "act": 1.5, "done": 0.0}  # relative pause after a kind

router = APIRouter()

_seq: dict[str, int] = {}
_subs: dict[str, list[asyncio.Queue[ActivityEvent]]] = {}


def events_path(run_id: str) -> Path:
    return Path(get_settings().data_dir) / "runs" / run_id / "events.jsonl"


def load_events(run_id: str) -> list[ActivityEvent]:
    p = events_path(run_id)
    if not p.exists():
        return []
    return [ActivityEvent.model_validate_json(line) for line in p.read_text().splitlines() if line.strip()]


def _truncate(msg: str) -> str:
    msg = " ".join(msg.split())
    return msg if len(msg) <= MAX_MESSAGE else msg[: MAX_MESSAGE - 1] + "…"


def emit(
    run_id: str,
    agent: str,
    kind: EventKind,
    message: str,
    building_id: str | None = None,
    evidence_id: str | None = None,
    *,
    building_name: str | None = None,
) -> ActivityEvent:
    """Record one activity event (sync, safe to call from async code)."""
    if run_id not in _seq:  # continue numbering after a restart
        _seq[run_id] = len(load_events(run_id))
    seq = _seq[run_id]
    _seq[run_id] = seq + 1
    ev = ActivityEvent(
        ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        run_id=run_id, seq=seq, agent=agent, building_id=building_id, building_name=building_name,
        kind=kind, message=_truncate(message), evidence_id=evidence_id,
    )
    p = events_path(run_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(ev.model_dump_json() + "\n")
    for q in _subs.get(run_id, []):
        q.put_nowait(ev)
    return ev


def reset_run(run_id: str) -> None:
    """Forget in-memory state for a run (tests)."""
    _seq.pop(run_id, None)
    _subs.pop(run_id, None)


def _sse(ev: ActivityEvent) -> dict:
    # No SSE "event:" name, so a plain EventSource.onmessage receives every kind.
    return {"id": str(ev.seq), "data": ev.model_dump_json()}


async def live_stream(run_id: str) -> AsyncIterator[ActivityEvent]:
    """Past events first, then new ones, until a `done` event."""
    q: asyncio.Queue[ActivityEvent] = asyncio.Queue()
    past = load_events(run_id)  # no await between this read and subscribing: emit() is sync
    _subs.setdefault(run_id, []).append(q)
    try:
        for ev in past:
            yield ev
            if ev.kind == "done":
                return
        while True:
            ev = await q.get()
            yield ev
            if ev.kind == "done":
                return
    finally:
        _subs[run_id].remove(q)


def pace(events: list[ActivityEvent], total_s: float = REPLAY_TOTAL_S) -> list[float]:
    """Pause after each event so a replay lasts about `total_s` (30-40 s for a real run).

    Pauses are weighted by kind (a send_back dwells longer so the audience can read it), then clamped to
    [REPLAY_MIN_DELAY_S, REPLAY_MAX_DELAY_S]; very short runs therefore finish faster than `total_s`.
    The last event has no pause.
    """
    if not events:
        return []
    w = [DWELL.get(e.kind, 1.0) for e in events[:-1]]
    scale = total_s / (sum(w) or 1.0)
    return [min(REPLAY_MAX_DELAY_S, max(REPLAY_MIN_DELAY_S, x * scale)) if x else 0.0 for x in w] + [0.0]


async def replay_stream(run_id: str, delay: float | None = None) -> AsyncIterator[ActivityEvent]:
    events = load_events(run_id)
    delays = [delay] * len(events) if delay is not None else pace(events)
    for ev, d in zip(events, delays):
        yield ev
        await asyncio.sleep(d)


@router.get("/events/{run_id}")
async def stream_events(run_id: str, replay: int = Query(0), delay: float | None = Query(None, ge=0)):
    source = replay_stream(run_id, delay) if replay else live_stream(run_id)

    async def gen():
        async for ev in source:
            yield _sse(ev)

    return EventSourceResponse(gen(), ping=15)
