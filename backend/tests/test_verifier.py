"""Verifier loop through the real survey subgraph, with Gemini faked per claim field."""
import json
import re

import pytest

from app.agents import aerial, graph, records, verifier
from app.config import get_settings
from app.events import load_events, reset_run
from tests.test_aerial import obs, overhead, profile

# score sequence per field, consumed one per verify round
SCORES = {
    "roof.type": [0.95],                # verified first time
    "roof.color": [0.5, 0.85],          # sent back once, then verified
    "roof.usable_fraction": [0.5, 0.5, 0.5],  # sent back twice, then unverified
    "roof.shading": [0.1],              # rejected
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    ov = overhead(tmp_path)
    calls = {"reinspect": 0}
    seq = {k: list(v) for k, v in SCORES.items()}

    async def fake_records(bid, run_id=None):
        return profile()

    async def fake_inspect(p, run_id=None):
        o = obs(existing_solar=aerial.SolarObs(value="unknown", confidence=0.2))
        f, c = aerial.build_findings(p, o, [ov])
        return aerial.AerialResult(images=[ov], obs=o, findings=f, claims=c)

    async def fake_vision(prompt, images, schema):
        if schema is verifier.VerifierBatch:
            if calls.get("fail_verifier"):
                raise RuntimeError("429 RESOURCE_EXHAUSTED")
            pairs = re.findall(r"claim_id `([^`]+)`: field `([^`]+)`", prompt)
            return verifier.VerifierBatch(verdicts=[
                verifier.ClaimVerdict(claim_id=cid, score=seq[f].pop(0), note="checked",
                                      question_back=f"Is the {f} really as claimed near the 99th parking bay?")
                for cid, f in pairs])
        calls["reinspect"] += 1
        return obs()

    monkeypatch.setattr(records, "run", fake_records)
    monkeypatch.setattr(aerial, "inspect", fake_inspect)
    monkeypatch.setattr(verifier.llm, "vision_json", fake_vision)
    monkeypatch.setattr(aerial.llm, "vision_json", fake_vision)
    monkeypatch.setattr(graph, "_interior", lambda: None)
    yield tmp_path, calls
    get_settings.cache_clear()


async def test_verifier_loop_outcomes(env):
    tmp_path, calls = env
    reset_run("v1")
    out = await graph.build_survey_graph().ainvoke({"run_id": "v1", "building_id": "23551", "hero": False})
    by = {c.field: c for c in out["claims"]}
    assert by["roof.type"].status == "verified" and by["roof.type"].loops == 0
    assert by["roof.color"].status == "verified" and by["roof.color"].loops == 1
    assert by["roof.usable_fraction"].status == "unverified" and by["roof.usable_fraction"].loops == 2
    assert by["roof.shading"].status == "rejected"
    assert by["roof.existing_solar"].status == "unverified"  # value unknown → nothing to verify
    assert calls["reinspect"] == 2  # one batched call per round (round 1: color + usable; round 2: usable)

    ev = load_events("v1")
    sb = [e for e in ev if e.kind == "send_back"]
    assert len(sb) == 3 and all(e.agent == "Verifier" for e in sb)
    # the model's invented number ("99th") is replaced by a generic question
    assert all("99" not in e.message and e.message.startswith('sent back: "Re-check') for e in sb)
    assert sum(e.kind == "observe" and e.message.startswith("re-check:") for e in ev) == 3

    d = tmp_path / "data" / "buildings" / "23551"
    log = json.loads((d / "verification_log.json").read_text())
    assert [r["status"] for r in log if r["field"] == "roof.color"] == ["sent_back", "verified"]
    saved = {c["field"]: c["status"] for c in json.loads((d / "claims.json").read_text())}
    # verification.json is the resolver's contract: list[Claim] with final statuses
    from pydantic import TypeAdapter
    from app.schemas.claims import Claim
    final = TypeAdapter(list[Claim]).validate_json((d / "verification.json").read_text())
    assert {c.field: c.status for c in final} == saved
    assert saved["roof.shading"] == "rejected"
    # solar depends on rejected/unverified claims → excluded from the optimizer
    ups = {u["type"]: u for u in json.loads((d / "feasibility.json").read_text())}
    assert ups["rooftop_solar"]["include_in_optimizer"] is False


def test_safe_question_keeps_claim_numbers():
    p = profile()
    c = aerial.build_findings(p, obs(), [])[1][2]  # usable fraction 0.6
    state = {"profile": p}
    assert verifier.safe_question("Is the open area really 0.6 of the roof?", c, state) == \
        "Is the open area really 0.6 of the roof?"
    assert verifier.safe_question("Is it 12 panels?", c, state).startswith("Re-check usable fraction")
    assert verifier.safe_question(None, c, state).startswith("Re-check")


async def test_verifier_error_never_sends_back(env):
    tmp_path, calls = env
    calls["fail_verifier"] = True
    reset_run("v2")
    out = await graph.build_survey_graph().ainvoke({"run_id": "v2", "building_id": "23551", "hero": False})
    assert all(c.status == "unverified" for c in out["claims"])
    kinds = [e.kind for e in load_events("v2")]
    assert "send_back" not in kinds and "error" in kinds and calls["reinspect"] == 0
