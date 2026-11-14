"""Replay a recorded run's activity feed at demo pace (~30-40 s), offline.

  python scripts/replay_demo.py                 # the run with the most events under data/runs/
  python scripts/replay_demo.py run_7           # a specific run id
  python scripts/replay_demo.py --file path/to/events.jsonl --total 35
  python scripts/replay_demo.py --fast          # no pauses (checking the format)

Prints `Agent · Building · message` per event, coloured by kind (App Flow §7). Needs no network, keys
or cache: it only reads data/runs/<run_id>/events.jsonl. The frontend gets the same pacing from
GET /events/{run_id}?replay=1 (both use app.events.pace).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.events import REPLAY_TOTAL_S, pace  # noqa: E402
from app.schemas.events import ActivityEvent  # noqa: E402

COLORS = {"plan": 37, "decide": 37, "fetch": 34, "observe": 34, "verify": 32, "send_back": 33, "error": 31,
          "act": 35, "price": 36, "compose": 36, "done": 32}


def read_events(path: Path) -> list[ActivityEvent]:
    return [ActivityEvent.model_validate_json(l) for l in path.read_text().splitlines() if l.strip()]


def pick_run(runs_dir: Path) -> Path:
    files = sorted(runs_dir.glob("*/events.jsonl"), key=lambda p: sum(1 for _ in p.open()), reverse=True)
    if not files:
        sys.exit(f"no recorded runs under {runs_dir}")
    return files[0]


def format_event(ev: ActivityEvent, color: bool = True) -> str:
    line = " · ".join(x for x in (ev.agent, ev.building_name or ev.building_id, ev.message) if x)
    return f"\033[{COLORS.get(ev.kind, 37)}m{line}\033[0m" if color else line


def replay(events: list[ActivityEvent], total_s: float, *, fast: bool = False, out=sys.stdout, color: bool | None = None,
           sleep=time.sleep) -> float:
    """Print events with pacing; returns the total pause time."""
    color = out.isatty() if color is None else color
    delays = pace(events, total_s)
    for ev, d in zip(events, delays):
        print(format_event(ev, color), file=out, flush=True)
        if not fast:
            sleep(d)
    return 0.0 if fast else sum(delays)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_id", nargs="?")
    ap.add_argument("--file", type=Path)
    ap.add_argument("--total", type=float, default=REPLAY_TOTAL_S, help="target seconds (default %(default)s)")
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    runs = Path(get_settings().data_dir) / "runs"
    path = a.file or (runs / a.run_id / "events.jsonl" if a.run_id else pick_run(runs))
    if not path.exists():
        sys.exit(f"{path} not found")
    events = read_events(path)
    print(f"# replaying {path} ({len(events)} events)", file=sys.stderr)
    took = replay(events, a.total, fast=a.fast)
    print(f"# done, {took:.0f} s of pauses", file=sys.stderr)


if __name__ == "__main__":
    main()
