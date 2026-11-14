"""Verifier loop (T2.2).

verify(): the pending claims of a building, grouped by inspector, go to Gemini in ONE call per
group with their evidence images (inspector marks drawn on, numbered by claim) →
  score ≥ THRESHOLD           → verified
  score < REJECT              → rejected
  else, loops < MAX_LOOPS     → sent_back with a specific question (send_back event)
  else                        → unverified
Claims whose value is "unknown" have nothing to check → unverified.
A verifier error (rate limit, bad JSON, missing verdict) never sends a claim back: the claim
becomes unverified with a note, and an error event is emitted.
reinspect(): each inspector re-answers only its sent-back claims (one call per inspector), given
the verifier's questions; the graph then verifies again. verification_log.json keeps every round;
verification.json (written at finalize, read by the widget resolver) = list[Claim], final statuses.

The verifier's score is an internal number; it is stored, never shown in feed text.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from pydantic import BaseModel

from app.adapters.cache import write_json_atomic
from app.adapters.types import ImageRef
from app.agents import aerial, llm, store
from app.config import get_settings
from app.events import emit
from app.guardrails import check_numbers
from app.schemas.claims import Claim

log = logging.getLogger(__name__)
AGENT = "Verifier"
PROMPT_PATH = Path(__file__).parent / "prompts" / "verifier.md"
MAX_LOOPS = 2
REJECT = 0.3

FIELD_HELP = {
    "roof.type": "roof shape: flat, pitched or mixed",
    "roof.color": "roof surface colour: dark or light (reflective)",
    "roof.usable_fraction": "share of the roof open enough to host solar panels",
    "roof.shading": "shadow cast on the roof by neighbours, trees or rooftop structures",
    "roof.existing_solar": "whether PV panels are already on the roof",
    "interior.lighting": "type of light fixtures visible",
    "interior.hvac": "visible heating/cooling equipment",
    "interior.window": "window glazing type: single or double pane",
}
PALETTE = [(255, 0, 255), (255, 200, 0), (0, 230, 255), (255, 80, 80), (80, 255, 80), (255, 140, 0)]


def threshold() -> float:
    return float(os.environ.get("VERIFIER_THRESHOLD", "0.7"))


class ClaimVerdict(BaseModel):
    claim_id: str
    score: float
    note: str
    question_back: str | None = None


class VerifierBatch(BaseModel):
    verdicts: list[ClaimVerdict]


def _images(state: dict) -> dict[str, ImageRef]:
    imgs = list(state["aerial"].images)
    if state.get("interior"):
        imgs += list(state["interior"].images)
    return {i.image_id: i for i in imgs}


def marked_image(img: ImageRef, numbered: list[tuple[int, Claim]]) -> ImageRef:
    """Copy of an evidence image with each claim's marks drawn and labelled #n; cached by content."""
    boxes = [(n, m.bbox) for n, c in numbered for m in c.marks if m.image_id == img.image_id and m.bbox]
    if not boxes:
        return img
    key = hashlib.sha256(f"{img.image_id}{boxes}".encode()).hexdigest()[:16]
    out = Path(get_settings().cache_dir) / "media" / "verify" / f"{key}.jpg"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(img.local_path) as im:
            im = im.convert("RGB")
        w, h = im.size
        d = ImageDraw.Draw(im)
        lw = max(3, w // 300)
        for n, (x0, y0, x1, y1) in boxes:
            col = PALETTE[(n - 1) % len(PALETTE)]
            d.rectangle([x0 * w, y0 * h, x1 * w, y1 * h], outline=col, width=lw)
            d.text((x0 * w + lw + 2, y0 * h + lw + 2), f"#{n}", fill=col)
        im.save(out, quality=90)
    return img.model_copy(update={"image_id": f"{img.image_id}~{key}", "local_path": str(out)})


def _value(c: Claim) -> str:
    return json.dumps(c.value)


def prompt_for(state: dict, numbered: list[tuple[int, Claim]]) -> str:
    p = state["profile"]
    lines = []
    for n, c in numbered:
        marks = "; ".join(f"{m.label} on {m.image_id}" for m in c.marks) or "no specific region"
        lines.append(f"#{n} claim_id `{c.claim_id}`: field `{c.field}` "
                     f"({FIELD_HELP.get(c.field, c.field.replace('.', ' '))}) = {_value(c)}; "
                     f"inspector confidence {c.confidence:.2f}; looked at: {marks}")
    ctx = f"- {p.name}: {p.property_type}, {p.stories or '?'} stories, built {p.year_built or '?'}"
    return (PROMPT_PATH.read_text()
            .replace("{{claims}}", "\n".join(lines))
            .replace("{{context}}", ctx))


def _label(claim: Claim) -> str:
    field = claim.field.split(".", 1)[-1].replace("_", " ")
    v = claim.value
    if isinstance(v, bool):
        v = "yes" if v else "no"
    elif isinstance(v, float):
        v = f"{v:.0%}" if "fraction" in claim.field or "glazing" in claim.field else f"{v:g}"
    return f"{field} {v}"


def safe_question(q: str | None, claim: Claim, state: dict) -> str:
    sources = {"claim": claim.model_dump(), "profile": state["profile"].model_dump()}
    q = " ".join((q or "").split())
    if not q or check_numbers(q, sources):
        q = f"Re-check {claim.field.split('.', 1)[-1].replace('_', ' ')}: does the image support it?"
    return q[:200]


async def check_group(state: dict, claims: list[Claim]) -> dict[str, ClaimVerdict] | None:
    """One Gemini call for a group of claims (same inspector). None on failure."""
    numbered = list(enumerate(claims, start=1))
    imgs = _images(state)
    ids = sorted({i for c in claims for i in c.evidence_ids if i in imgs})
    if not ids:
        return None
    evidence = [marked_image(imgs[i], numbered) for i in ids]
    try:
        out = await llm.vision_json(prompt_for(state, numbered), evidence, VerifierBatch)
    except Exception as e:  # noqa: BLE001
        log.warning("verifier failed on %s: %s", state["building_id"], e)
        return None
    return {v.claim_id: v.model_copy(update={"score": min(1.0, max(0.0, v.score))}) for v in out.verdicts}


def _log(building_id: str, rows: list[dict], fresh: bool) -> None:
    p = store.building_dir(building_id) / "verification_log.json"
    cur = json.loads(p.read_text()) if (p.exists() and not fresh) else []
    write_json_atomic(p, cur + rows)


async def verify(state: dict) -> dict:
    run_id, profile, bid = state["run_id"], state["profile"], state["building_id"]
    th = threshold()

    def ev(kind, msg, evidence=None):
        emit(run_id, AGENT, kind, msg, bid, evidence, building_name=profile.name)

    claims = list(state["claims"])
    todo = [c for c in claims if c.status in ("pending", "sent_back")]
    checkable = [c for c in todo if c.value != "unknown"]
    verdicts: dict[str, ClaimVerdict] = {}
    failed = False
    for agent in sorted({c.agent for c in checkable}):
        got = await check_group(state, [c for c in checkable if c.agent == agent])
        if got is None:
            failed = True
        else:
            verdicts.update(got)
    if failed:
        ev("error", "verifier unavailable for some claims; left unverified")

    sent_back: dict[str, str] = {}
    rows = []
    by_id = {c.claim_id: i for i, c in enumerate(claims)}
    for c in todo:
        i = by_id[c.claim_id]
        ev_id = c.evidence_ids[0] if c.evidence_ids else None
        if c.value == "unknown":
            claims[i] = c.model_copy(update={"status": "unverified", "verifier_note": "nothing observed to verify"})
            continue
        v = verdicts.get(c.claim_id)
        if v is None:  # verifier error / missing verdict: never a send-back
            claims[i] = c.model_copy(update={"status": "unverified", "verifier_note": "verifier unavailable"})
            continue
        upd: dict[str, Any] = {"verifier_score": round(v.score, 3), "verifier_note": v.note[:200]}
        if v.score >= th:
            upd["status"] = "verified"
            ev("verify", f"verified: {_label(c)}", ev_id)
        elif v.score < REJECT:
            upd["status"] = "rejected"
            ev("verify", f"rejected: {_label(c)}", ev_id)
        elif c.loops < MAX_LOOPS:
            q = safe_question(v.question_back, c, state)
            upd["status"] = "sent_back"
            sent_back[c.claim_id] = q
            ev("send_back", f'sent back: "{q}"', ev_id)
        else:
            upd["status"] = "unverified"
            ev("verify", f"unverified after {MAX_LOOPS} re-checks: {_label(c)}", ev_id)
        claims[i] = c.model_copy(update=upd)
        rows.append({"claim_id": c.claim_id, "field": c.field, "value": c.value, "loop": c.loops,
                     "score": round(v.score, 3), "note": v.note, "status": upd["status"],
                     "question": sent_back.get(c.claim_id)})
    _log(bid, rows, fresh=not state.get("_verify_round"))
    return {"claims": claims, "sent_back": sent_back, "_verify_round": (state.get("_verify_round") or 0) + 1}


def _merge_meta(c: Claim, o: Claim) -> Claim:
    return c.model_copy(update={"status": o.status, "verifier_score": o.verifier_score,
                                "loops": o.loops, "verifier_note": o.verifier_note})


async def reinspect(state: dict) -> dict:
    """Each inspector re-answers its sent-back claims (one call per inspector)."""
    run_id, profile, bid = state["run_id"], state["profile"], state["building_id"]
    old = {c.claim_id: c for c in state["claims"]}
    asks = [(old[cid], q) for cid, q in state["sent_back"].items()]
    res = state["aerial"]
    interior_res = state.get("interior")
    aerial_asks = [(c, q) for c, q in asks if c.agent == "aerial"]
    interior_asks = [(c, q) for c, q in asks if c.agent == "interior"]
    if aerial_asks:
        res = await aerial.reinspect(profile, res, aerial_asks)
    if interior_asks and interior_res is not None:
        from app.agents import interior
        interior_res = await interior.reinspect(profile, interior_res, interior_asks)

    rebuilt = {c.claim_id: c for c in res.claims}
    if interior_res is not None:
        rebuilt.update({c.claim_id: c for c in interior_res.claims})
    claims = []
    for cid, o in old.items():
        n = rebuilt.get(cid, o)
        if cid in state["sent_back"]:
            n = n.model_copy(update={"status": "pending", "loops": o.loops + 1,
                                     "verifier_score": o.verifier_score, "verifier_note": o.verifier_note})
            emit(run_id, "Aerial" if o.agent == "aerial" else "Interior", "observe",
                 f"re-check: {_label(n)}", bid, n.evidence_ids[0] if n.evidence_ids else None,
                 building_name=profile.name)
        else:
            n = _merge_meta(n, o)
        claims.append(n)
    return {"claims": claims, "aerial": res, "interior": interior_res, "sent_back": {}}


def refresh_findings(state: dict) -> dict:
    """After the loop: carry final statuses onto the inspectors' results (claims, pins)."""
    by_id = {c.claim_id: c for c in state["claims"]}
    res = state["aerial"]
    out = {"aerial": res.model_copy(update={"claims": [by_id.get(c.claim_id, c) for c in res.claims]})}
    if state.get("interior") is not None:
        from app.agents import interior
        out["interior"] = interior.with_statuses(state["interior"], by_id)
    return out
