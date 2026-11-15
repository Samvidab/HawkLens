from typing import Literal

from pydantic import BaseModel

EventKind = Literal["plan", "fetch", "observe", "decide", "verify", "send_back", "price", "compose", "act", "error", "done"]


class ActivityEvent(BaseModel):  # data/runs/<run_id>/events.jsonl, streamed over SSE
    ts: str
    run_id: str
    seq: int
    agent: str
    building_id: str | None = None
    building_name: str | None = None
    kind: EventKind
    message: str  # <= 90 chars, factual, no chatter
    evidence_id: str | None = None
