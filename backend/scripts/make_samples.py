"""Generate sample layout JSONs (one per situation) from a synthetic portfolio + the STUB engine.

  python scripts/make_samples.py [--out ../docs/agent/samples]

Runs the real pipeline (site-engineer rules -> pricing -> replan -> composer -> resolver) on four
synthetic buildings in a temp data dir, with Gemini disabled (stock `why` lines, fallback memo), so
output is deterministic and needs no keys or network. NOT real CoStar data; pricing is the stub's, except
the approved sample, which the real engine prices (sample pricing cannot be approved).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXED_TS = "2026-11-14T15:02:11Z"
DATA = Path(tempfile.mkdtemp(prefix="retroalpha-samples-"))
os.environ.update(DATA_DIR=str(DATA), CACHE_DIR=str(DATA / "cache"), ENGINE_MODE="stub", NESSIE_MODE="stub", CACHE_MODE="off")

from app.adapters.geometry import square_wkt  # noqa: E402
from app.agents import composer, memo, replan  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.integrations import engine_client, nessie_client  # noqa: E402
from app.rules.feasibility import evaluate  # noqa: E402
from app.schemas import (AerialFindings, BuildingProfile, Claim, FacadeFinding, InteriorFindings, Mark, OwnerAction, Pin)  # noqa: E402
from app.storage import write_json  # noqa: E402
from app.widgets.registry import json_schemas  # noqa: E402

# (id, name, lat, lon, stories, rba_sqft, year, hero?, roof m2, roof colour, shading, S glazing)
BUILDINGS = [
    ("b1", "Sample Tower", 29.7604, -95.3698, 30, 900_000, 1982, True, 2400, "dark", "none", 0.55),
    ("b2", "Sample Plaza", 29.7551, -95.3655, 12, 310_000, 1998, False, 1500, "dark", "partial", 0.40),
    ("b3", "Sample Lofts", 29.7498, -95.3601, 8, 140_000, 2008, False, 600, "light", "none", 0.45),
    ("b4", "Sample Annex", 29.7650, -95.3560, 5, 90_000, 1975, False, 420, "dark", "heavy", 0.20),
]


def claim(cid, bid, agent, field, value, status="verified", conf=0.85, img="vxo_" , note=None, bbox=(0.2, 0.2, 0.7, 0.6)):
    image = f"{img}{bid}_1" if agent == "aerial" else f"pano_{bid}_1"
    return Claim(claim_id=cid, building_id=bid, agent=agent, field=field, value=value, confidence=conf, evidence_ids=[image],
                 marks=[Mark(image_id=image, label=field.split(".")[-1], bbox=bbox)], status=status, verifier_score=0.9 if status == "verified" else 0.2,
                 verifier_note=note)


def build_world(root: Path, *, issue: bool = False) -> None:
    for bid, name, lat, lon, stories, rba, year, hero, roof, color, shade, glaze in BUILDINGS:
        d = root / "buildings" / bid
        prof = BuildingProfile(building_id=bid, costar_id=f"SYNTH-{bid}", name=name, address=f"{100 + int(bid[1:])} Main St", city="Houston",
                               lat=lat, lon=lon, footprint_wkt=square_wkt(lat, lon, (rba / stories / 10.7639) ** 0.5, "Houston"),
                               footprint_source="estimated", property_type="Office", building_class="A", year_built=year, stories=stories,
                               rba_sqft=float(rba), occupancy_pct=88.0, matterport_model_id="SYNTH-MODEL" if hero else None,
                               source_fields={"stories": "NumberOfStories", "rba_sqft": "RBA", "year_built": "YearBuilt"})
        aer = AerialFindings(building_id=bid, roof_type="flat", roof_color=color, usable_roof_fraction=0.6, shading=shade, existing_solar=False,
                             usable_roof_m2=float(roof), facades={"S": FacadeFinding(glazing_ratio=glaze, window_count_est=stories * 6),
                                                                   "W": FacadeFinding(glazing_ratio=glaze - 0.1, window_count_est=stories * 4),
                                                                   "N": FacadeFinding(glazing_ratio=0.25, window_count_est=stories * 5)},
                             claim_ids=[], evidence_ids=[f"vxo_{bid}_1"])
        glaze_status = "rejected" if (issue and bid == "b3") else "verified"
        claims = [claim(f"{bid}-c1", bid, "aerial", "roof.existing_solar", False), claim(f"{bid}-c2", bid, "aerial", "roof.shading", shade),
                  claim(f"{bid}-c3", bid, "aerial", "roof.color", color), claim(f"{bid}-c4", bid, "aerial", "roof.type", "flat"),
                  claim(f"{bid}-c5", bid, "aerial", "facade.S.glazing", glaze, status=glaze_status, conf=0.7,
                        note="mostly spandrel panels, not glass" if glaze_status == "rejected" else None)]
        interior = None
        if hero:
            claims += [claim(f"{bid}-i1", bid, "interior", "interior.lighting_type", "fluorescent", conf=0.8),
                       claim(f"{bid}-i2", bid, "interior", "interior.hvac_visible", "rooftop_unit_old", conf=0.75)]
            interior = InteriorFindings(building_id=bid, model_id="SYNTH-MODEL", lighting_type="fluorescent", hvac_visible=["rooftop_unit_old"],
                                        window_type="double", floor_area_sqft=820_000.0, envelope_area_sqft=410_000.0,
                                        claim_ids=[f"{bid}-i1", f"{bid}-i2"], evidence_ids=["pano_b1_1"],
                                        pins=[Pin(claim_id="b1-i1", label="Fluorescent lighting", xyz=(4.2, 7.1, 2.6), status="verified"),
                                              Pin(claim_id="b1-i2", label="Older rooftop unit", xyz=(12.0, 3.4, 3.1), status="verified")])
            write_json(d / "rooms.json", [{"room_id": "r1", "type": "office", "polygon": [[0, 0], [10, 0], [10, 8], [0, 8]], "area_sqft": 860.0},
                                          {"room_id": "r2", "type": "corridor", "polygon": [[10, 0], [22, 0], [22, 3], [10, 3]], "area_sqft": 390.0},
                                          {"room_id": "r3", "type": "mechanical", "polygon": [[10, 3], [22, 3], [22, 8], [10, 8]], "area_sqft": 640.0}])
            write_json(d / "interior.json", interior)
            write_json(d / "interior_scan.json", {  # Lane A's scan summary: mesh urls + rooms (+ optional showcase_url)
                "model_id": "SYNTH-MODEL", "mesh_url": "/media/mesh/SYNTH-MODEL/model.obj", "mtl_url": "/media/mesh/SYNTH-MODEL/model.mtl",
                "rooms": [{"room_id": "r1", "type": "office", "area_sqft": 860.0, "height_m": 2.7},
                          {"room_id": "r2", "type": "corridor", "area_sqft": 390.0, "height_m": 2.7},
                          {"room_id": "r3", "type": "mechanical", "area_sqft": 640.0, "height_m": 3.0}]})
        ups = evaluate(prof, aer, interior, claims)
        # the verifier's final statuses decide verified/include_in_optimizer
        from app.rules.feasibility import apply_verification
        ups = apply_verification(ups, claims)
        write_json(d / "profile.json", prof); write_json(d / "aerial.json", aer)
        write_json(d / "verification.json", claims); write_json(d / "feasibility.json", ups)
    write_json(root / "portfolio.json", {"city": "Houston", "buildings": [{"building_id": b[0], "name": b[1], "hero": b[7]} for b in BUILDINGS]})


async def _llm_off(*a, **k):
    raise RuntimeError("LLM disabled for deterministic samples")


def finalize(layout: dict, name: str) -> dict:
    layout["generated_at"], layout["layout_id"] = FIXED_TS, f"lay_sample_{name}"
    return layout


async def act(run: str, type_: str, payload: dict | None = None) -> dict:
    return (await replan.replan(OwnerAction(run_id=run, type=type_, payload=payload or {}))).model_dump(mode="json")


def fresh(issue: bool = False) -> None:
    import shutil
    for sub in ("buildings", "plans", "runs", "memo", "finance"):
        shutil.rmtree(DATA / sub, ignore_errors=True)
    engine_client.reset_stub(); nessie_client.reset_stub(); get_settings.cache_clear()
    from app import events
    events._seq.clear(); events._subs.clear()
    build_world(DATA, issue=issue)


GOAL = {"city": "Houston", "target_pct": 25, "risk_lambda": 0.5}


async def generate(out: Path) -> dict[str, dict]:
    composer.text_json = _llm_off; memo.text_json = _llm_off
    samples: dict[str, dict] = {}

    fresh(); samples["portfolio_overview"] = await act("sample", "goal", GOAL)
    fresh(); samples["target_gap"] = await act("sample", "goal", {**GOAL, "target_pct": 90, "budget_usd": 400_000.0})
    fresh(issue=True); samples["verification_issue"] = await act("sample", "goal", GOAL)
    fresh(); await act("sample", "goal", GOAL)
    samples["building_detail"] = await act("sample", "open_building", {"building_id": "b1"})
    samples["building_detail_no_matterport"] = await act("sample", "open_building", {"building_id": "b3"})
    scan = DATA / "buildings/b1/interior_scan.json"  # Lane A supplies a Matterport tour link: hero_3d embeds it instead of the mesh
    write_json(scan, {**json.loads(scan.read_text()), "showcase_url": "https://my.matterport.com/show/?m=SYNTH-MODEL"})
    samples["building_detail_showcase"] = await act("sample", "open_building", {"building_id": "b1"})
    # Approval refuses stub (sample) pricing and infeasible plans, so the approved sample is priced by the real
    # quant engine at a target this synthetic portfolio can reach.
    fresh(); os.environ["ENGINE_MODE"] = "live"; get_settings.cache_clear()
    from app.engine import state as engine_state
    engine_state.clear()
    try:
        await act("sample", "goal", {**GOAL, "target_pct": 5})
        pid = json.loads((DATA / "plans/current.json").read_text())["plan_id"]
        samples["approved"] = await act("sample", "approve", {"plan_id": pid})
    finally:
        os.environ["ENGINE_MODE"] = "stub"; get_settings.cache_clear()

    out.mkdir(parents=True, exist_ok=True)
    for name, lay in samples.items():
        (out / f"{name}.json").write_text(json.dumps(finalize(lay, name), indent=2) + "\n")
    (out / "registry.json").write_text(json.dumps(json_schemas(), indent=2) + "\n")
    return samples


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT.parent / "docs" / "agent" / "samples")
    a = ap.parse_args()
    samples = asyncio.run(generate(a.out))
    for n, lay in samples.items():
        print(f"{n:32s} {lay['situation']:20s} {[w['type'] for w in lay['widgets']]}")


if __name__ == "__main__":
    main()
