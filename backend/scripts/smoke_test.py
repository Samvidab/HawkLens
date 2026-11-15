"""End-to-end smoke test of the HTTP API.

  python scripts/smoke_test.py                 # self-contained: starts the app on a free port with a synthetic
                                               # portfolio, stub engine/Nessie, Gemini OFF (deterministic, no keys)
  python scripts/smoke_test.py --engine live   # same, priced by the real quant engine (app.engine)
  python scripts/smoke_test.py --llm           # same, but let the composer/memo call Gemini (needs backend/.env)
  python scripts/smoke_test.py --url https://api.example.com --run-id smoke_1
                                               # test a running server with ITS data (situations are not asserted)

Flow: /health, /registry, /portfolio -> open the live SSE stream -> POST /compose for every action type
(goal, include_unverified, set_target, set_budget, set_risk, exclude/include_building, toggle_upgrade,
select_bar, open_building, target gap, approve (+ stale plan_id, repeat approve), bad input) -> check each
layout against the schema + widget registry and the 3 s budget -> GET /state -> compare the live event stream
with the recorded one. Exit code 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

import httpx  # noqa: E402

BUDGET_S = 3.0
EVENT_KINDS = {"plan", "fetch", "observe", "decide", "verify", "send_back", "price", "compose", "act", "error", "done"}


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""), flush=True)
        return bool(ok)

    @property
    def failed(self) -> list[str]:
        return [n for n, ok, _ in self.rows if not ok]


def w_of(layout: dict, t: str) -> dict | None:
    return next((w["props"] for w in layout["widgets"] if w["type"] == t), None)


async def run(base: str, run_id: str, strict: bool, live_engine: bool = False) -> Report:
    from app.schemas.layout import Layout
    from app.widgets.registry import validate_layout
    rep = Report()
    live: list[dict] = []
    async with httpx.AsyncClient(base_url=base, timeout=30) as c:
        r = await c.get("/health")
        rep.check("GET /health", r.status_code == 200 and r.json().get("status") == "ok", str(r.json()))
        reg = (await c.get("/registry")).json()
        rep.check("GET /registry lists the widgets", {"plan_table", "activity_feed", "hero_3d"} <= set(reg["widgets"]))
        pf = await c.get("/portfolio")
        rep.check("GET /portfolio", pf.status_code in (200, 404), f"HTTP {pf.status_code}")

        async def listen():
            async with httpx.AsyncClient(base_url=base, timeout=None) as sc, sc.stream("GET", f"/events/{run_id}") as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        live.append(json.loads(line[5:]))
        listener = asyncio.create_task(listen())
        await asyncio.sleep(0.3)

        async def act(name: str, type_: str, payload: dict | None = None, *, expect: int = 200, situation: str | None = None):
            t0 = time.perf_counter()
            r = await c.post("/compose", json={"run_id": run_id, "type": type_, "payload": payload or {}})
            dt = time.perf_counter() - t0
            rep.check(f"{name}: HTTP {expect}", r.status_code == expect, f"got {r.status_code} {r.text[:120] if r.status_code != expect else ''}")
            if r.status_code != 200 or expect != 200:
                return None
            lay = r.json()
            try:
                validate_layout(Layout.model_validate(lay)); valid = True
            except Exception as e:  # noqa: BLE001
                valid = False; print("      ", str(e)[:200])
            rep.check(f"{name}: layout valid, feed last", valid and lay["widgets"][-1]["type"] == "activity_feed")
            rep.check(f"{name}: under {BUDGET_S:g} s", dt < BUDGET_S, f"{dt * 1000:.0f} ms")
            if situation and strict:
                # with the real engine, whether a target is reachable depends on its numbers: overview or target_gap
                ok_set = {situation, "target_gap"} if (live_engine and situation == "portfolio_overview") else {situation}
                rep.check(f"{name}: situation == {situation}", lay["situation"] in ok_set, lay["situation"])
            print(f"      {lay['situation']:20s} {[w['type'] for w in lay['widgets']]}", flush=True)
            return lay

        g = await act("goal", "goal", {"city": "Houston", "target_pct": 25, "risk_lambda": 0.5}, situation="verification_issue" if strict else None)
        if g is None:
            listener.cancel(); return rep
        bids = [b["building_id"] for b in (w_of(g, "portfolio_3d") or {"buildings": []})["buildings"]]
        rep.check("layout lists buildings", len(bids) >= 2, str(bids))

        # find an unverified upgrade and a Matterport building by looking at the detail screens
        unverified, hero = None, None
        for b in bids:
            d = await act(f"open_building {b}", "open_building", {"building_id": b}, situation="building_detail")
            if d:
                hero = hero or (b if w_of(d, "hero_3d") else None)
                uid = next((u["upgrade"]["upgrade_id"] for u in (w_of(d, "upgrade_list") or {"upgrades": []})["upgrades"]
                            if u["upgrade"]["verified"] == "unverified"), None)
                if uid and not unverified:
                    unverified = (b, uid)
        if strict:
            rep.check("a hero building with hero_3d exists", hero is not None)
            rep.check("an unverified upgrade exists", unverified is not None)
        if unverified:
            ub, uu = unverified
            await act(f"open_building {ub} (owner of the unverified upgrade)", "open_building", {"building_id": ub})
            # includes made on a detail screen keep that screen open
            lay = await act("include_unverified", "include_unverified", {"upgrade_id": uu}, situation="building_detail")
            if lay:
                row = next((u for u in w_of(lay, "upgrade_list")["upgrades"] if u["upgrade"]["upgrade_id"] == uu), None)
                rep.check("included unverified upgrade is flagged owner-included", row is not None and row["owner_included"] is True)
        await act("open_building null (back)", "open_building", {"building_id": None}, situation="portfolio_overview")
        lay = await act("set_target", "set_target", {"target_pct": 30}, situation="portfolio_overview")
        rep.check("set_target applied", lay is not None and w_of(lay, "target_control")["target_pct"] == 30)
        await act("set_budget", "set_budget", {"budget_usd": 3_000_000.0})
        await act("set_risk", "set_risk", {"risk_lambda": 0.8})
        lay = await act("exclude_building", "exclude_building", {"building_id": bids[1]})
        if lay:
            ex = {b["building_id"]: b["excluded"] for b in w_of(lay, "portfolio_3d")["buildings"]}
            rep.check("excluded building is greyed out", ex.get(bids[1]) is True)
        await act("include_building", "include_building", {"building_id": bids[1]})
        rows = (w_of(lay or g, "plan_table") or {"rows": []})["rows"]
        if rows:
            uid = rows[0]["upgrade_id"]
            await act("toggle_upgrade off", "toggle_upgrade", {"upgrade_id": uid, "on": False})
            lay = await act("toggle_upgrade on", "toggle_upgrade", {"upgrade_id": uid, "on": True})
            bar = next(iter((w_of(lay, "abatement_curve") or {"bars": []})["bars"]), None) if lay else None
            if bar:
                sel = await act("select_bar", "select_bar", {"upgrade_id": bar["upgrade_id"]}, situation="building_detail")
                rep.check("select_bar focuses that building", sel is not None and sel["focus_building_id"] == bar["building_id"])
        await act("open_building null (back)", "open_building", {"building_id": None})
        await act("set_target 90", "set_target", {"target_pct": 90})
        await act("set_budget 400k -> target gap", "set_budget", {"budget_usd": 400_000.0}, situation="target_gap")

        await act("fresh goal", "goal", {"city": "Houston", "target_pct": 25, "risk_lambda": 0.5})
        st = (await c.get(f"/state/{run_id}")).json()
        plan_id = st.get("plan_id")
        rep.check("GET /state has the plan id and layout", bool(plan_id) and st["layout"]["widgets"], str(plan_id))
        await act("approve with a stale plan_id", "approve", {"plan_id": "plan_stale"}, expect=409)
        stub_pricing = strict and not live_engine
        pv = (await c.get("/plan")).json()
        rep.check("GET /plan is the plan in /state", pv.get("plan_id") == plan_id, str(pv.get("plan_id")))
        ap = None
        if stub_pricing:  # sample pricing must never be fundable
            rep.check("GET /plan says stub pricing is not approvable", pv["approval"]["approvable"] is False)
            await act("approve a stub-priced plan is refused", "approve", {"plan_id": plan_id}, expect=409)
        else:
            if pv.get("status") != "ok":  # an infeasible plan must be refused, then a reachable target funded
                rep.check("GET /plan says an infeasible plan is not approvable", pv["approval"]["approvable"] is False)
                await act("approve an infeasible plan is refused", "approve", {"plan_id": plan_id}, expect=409)
                await act("reachable goal", "goal", {"city": "Houston", "target_pct": 5, "risk_lambda": 0.5})
                pv = (await c.get("/plan")).json()
                plan_id = pv.get("plan_id")
            rep.check("GET /plan approvable for a feasible engine plan", pv["approval"]["approvable"] is True,
                      "; ".join(pv["approval"]["reasons"]))
            rep.check("plan line items reconcile to total_upfront", pv.get("reconciles") is True and
                      abs(sum(r["upfront_usd"] for r in pv["line_items"]) - pv["total_upfront"]) < 0.01)
            ap = await act("approve", "approve", {"plan_id": plan_id}, situation="approved")
        if ap:
            fc = w_of(ap, "financing_card")
            rep.check("financing executed with Nessie ids", fc["state"] == "executed" and bool(fc["nessie_ids"]), str(list((fc["nessie_ids"] or {}))[:2]))
            rep.check("memo present", "Retrofit plan memo" in (w_of(ap, "memo") or {"markdown": ""})["markdown"])
            again = await act("approve again (idempotent)", "approve", {"plan_id": plan_id}, situation="approved")
            rep.check("repeat approve returns the same ids", again is not None and w_of(again, "financing_card")["nessie_ids"] == fc["nessie_ids"])
        await act("unknown action type", "chat", {}, expect=422)
        await act("bad payload", "set_target", {"target_pct": "lots"}, expect=422)
        await act("unknown building", "exclude_building", {"building_id": "nope"}, expect=422)
        st = (await c.get(f"/state/{run_id}")).json()
        rep.check("GET /state matches the last layout", ap is None or st["layout"]["layout_id"] == ap["layout_id"])
        rep.check("GET /state 404 for an unknown run", (await c.get("/state/no_such_run")).status_code == 404)

        # events: the live stream saw everything, in order, with legal kinds and short messages
        await asyncio.sleep(0.5)
        listener.cancel()
        replay = []
        async with c.stream("GET", f"/events/{run_id}?replay=1&delay=0") as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    replay.append(json.loads(line[5:]))
        rep.check("events were emitted", len(replay) >= 20, f"{len(replay)} events")
        rep.check("live stream == recorded events", [e["seq"] for e in live] == [e["seq"] for e in replay], f"{len(live)} live / {len(replay)} recorded")
        rep.check("event seq contiguous", [e["seq"] for e in replay] == list(range(len(replay))))
        rep.check("event kinds legal, messages <= 90 chars", all(e["kind"] in EVENT_KINDS and len(e["message"]) <= 90 for e in replay))
        speakers = {"Orchestrator", "Pricing", "Composer"} | (set() if stub_pricing else {"Finance"})
        rep.check(f"{', '.join(sorted(speakers))} all spoke", speakers <= {e["agent"] for e in replay})
    return rep


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


async def wait_ready(base: str, proc: subprocess.Popen | None, timeout: float = 30) -> None:
    t0 = time.time()
    async with httpx.AsyncClient() as c:
        while time.time() - t0 < timeout:
            if proc is not None and proc.poll() is not None:
                raise SystemExit("server exited during startup")
            try:
                if (await c.get(base + "/health")).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.3)
    raise SystemExit("server did not become ready")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", help="test an already running server instead of starting one")
    ap.add_argument("--run-id", default=f"smoke_{int(time.time())}")
    ap.add_argument("--engine", choices=["stub", "live"], default="stub", help="pricing engine for the self-contained server")
    ap.add_argument("--llm", action="store_true", help="allow real Gemini calls in the composer/memo (self-contained mode)")
    a = ap.parse_args()
    proc, log = None, None
    if a.url:
        base, strict = a.url.rstrip("/"), False
    else:
        import make_samples as ms  # synthetic world; sets DATA_DIR etc. in this process's environment
        ms.build_world(ms.DATA, issue=True)
        env = dict(os.environ, ENGINE_MODE=a.engine)
        if not a.llm:
            env.update(GEMINI_API_KEY="", GEMINI_MODEL_FAST="", GEMINI_MODEL_VISION="")  # fall back to templates, no network
        port = free_port(); base, strict = f"http://127.0.0.1:{port}", True
        log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--workers", "1"],
                                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(f"# started app on {base} (data: {ms.DATA}, log: {log.name})")
    try:
        asyncio.run(wait_ready(base, proc))
        rep = asyncio.run(run(base, a.run_id, strict, live_engine=(a.engine == 'live' and not a.url)))
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
    n = len(rep.rows)
    print(f"\n{'PASS' if not rep.failed else 'FAIL'}: {n - len(rep.failed)}/{n} checks" + (f"; failed: {rep.failed}" if rep.failed else ""))
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
