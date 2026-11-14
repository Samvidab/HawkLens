import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app import events
from app.events import pace
from app.schemas.events import ActivityEvent

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "replay_demo.py"
sys.path.insert(0, str(SCRIPT.parent))
import replay_demo  # noqa: E402


def evs(n, kinds=None):
    kinds = kinds or ["observe"] * n
    return [ActivityEvent(ts="t", run_id="r", seq=i, agent="Aerial", building_name="Allen Center", kind=kinds[i], message=f"m{i}")
            for i in range(n)]


@pytest.mark.parametrize("n", [30, 45, 60, 90])
def test_pace_lands_in_30_to_40_seconds_for_a_realistic_run(n):
    kinds = ["plan"] + ["fetch", "observe", "observe", "verify"] * ((n - 2) // 4) + ["send_back"] * 1
    kinds += ["observe"] * (n - 1 - len(kinds)) + ["done"]
    e = evs(n, kinds[:n])
    total = sum(pace(e))
    assert 30 <= total <= 40, total
    d = pace(e)
    assert d[-1] == 0 and len(d) == n


def test_send_back_dwells_longer_and_bounds_hold():
    e = evs(40, ["observe"] * 10 + ["send_back"] + ["observe"] * 29)
    d = pace(e)
    assert d[10] > d[0] * 2
    assert all(events.REPLAY_MIN_DELAY_S <= x <= events.REPLAY_MAX_DELAY_S for x in d[:-1])
    assert sum(pace(evs(5))) < 35 and pace([]) == [] and pace(evs(1)) == [0.0]  # tiny runs end sooner


def test_replay_prints_in_order_and_sleeps_the_paced_total():
    e = evs(40, ["plan"] + ["observe"] * 38 + ["done"])
    out, slept = io.StringIO(), []
    total = replay_demo.replay(e, 35, out=out, color=False, sleep=slept.append)
    lines = out.getvalue().splitlines()
    assert lines[0] == "Aerial · Allen Center · m0" and lines[-1].endswith("m39") and len(lines) == 40
    assert slept == pace(e) and total == pytest.approx(sum(slept)) and 30 <= total <= 40


def test_fast_flag_never_sleeps():
    slept = []
    replay_demo.replay(evs(5), 35, out=io.StringIO(), fast=True, sleep=slept.append)
    assert slept == []


def test_cli_replays_a_recorded_run(tmp_path):
    run = tmp_path / "runs" / "run_7"; run.mkdir(parents=True)
    (run / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in evs(6, ["plan", "fetch", "observe", "send_back", "observe", "done"])))
    other = tmp_path / "runs" / "short"; other.mkdir()
    (other / "events.jsonl").write_text(evs(2)[0].model_dump_json() + "\n")
    env = {"DATA_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    for args in (["run_7"], []):  # explicit id, and auto-pick of the longest run
        r = subprocess.run([sys.executable, str(SCRIPT), *args, "--fast"], capture_output=True, text=True, env=env, timeout=60)
        assert r.returncode == 0, r.stderr
        assert r.stdout.splitlines()[0] == "Aerial · Allen Center · m0" and len(r.stdout.splitlines()) == 6
        assert "run_7" in r.stderr
    bad = subprocess.run([sys.executable, str(SCRIPT), "nope", "--fast"], capture_output=True, text=True, env=env, timeout=60)
    assert bad.returncode != 0 and "not found" in bad.stderr


async def test_sse_replay_uses_the_same_pacing(tmp_path, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("DATA_DIR", str(tmp_path)); get_settings.cache_clear()
    events._seq.clear()
    for e in evs(4, ["plan", "send_back", "observe", "done"]):
        events.emit("rp", e.agent, e.kind, e.message)
    slept = []
    real = events.asyncio.sleep
    async def fake_sleep(d): slept.append(d); await real(0)
    monkeypatch.setattr(events.asyncio, "sleep", fake_sleep)
    got = [e.message async for e in events.replay_stream("rp")]
    assert got == ["m0", "m1", "m2", "m3"] and slept == pace(events.load_events("rp"))
    get_settings.cache_clear()
