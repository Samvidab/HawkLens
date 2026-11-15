# Demo script (2 minutes)

Every number below is in `docs/agent/PITCH-FACTS.md`. If a number isn't there, don't say it. ⚠ = changed for the 7-building portfolio (7900 Fannin dropped).

## Before going on stage

- **Backend, offline:** `cd backend && scripts/run_server.sh demo`. This sets `CACHE_MODE=read_only`, so there are no network or model calls; a cache miss is an error, not a live call.
- **Recorded run:** `run_id` **`warm_full`**.
  - The frontend must replay it: set `VITE_DEMO_RUN_ID=warm_full` in `frontend/.env.local`. It replays the feed at demo pace with `GET /events/warm_full?replay=1` and opens the layout saved on that run. ⚠ **Don't submit the goal live**: a live run has no building list, so it would survey and price all 8 buildings and replace the demo plan.
  - Terminal check, about 35 s: `python scripts/replay_demo.py warm_full`.
- ⚠ **Demo plan:** `5e46a8e9d761` in `data/plans/current.json`, 7 buildings at 40%, 7900 Fannin shown as excluded. Its memo is cached (`data/memo/5e46a8e9d761.md`), so Approve makes no model call. The read-only check `ro_seven` reproduced the plan, memo and widgets exactly.
- ⚠ **After any rehearsal, restore the demo state.** Every click writes to `warm_full` and `current.json`. From `backend/`: `rm -rf data/runs/warm_full && cp -rp data/demo_snapshot_7/runs/warm_full data/runs/ && cp -p data/demo_snapshot_7/plans/current.json data/plans/`.
- **Research lines:** these are a separate recorded run, `end_use_research` (5 lines, branch `emissions-3d`). Check them with `python scripts/replay_demo.py end_use_research`. They are **not** in the `warm_full` feed.
- **3D tags:** Lane B's CO₂ tour (branch `emissions-3d`) needs `VITE_EMISSIONS_3D=1` and `VITE_MATTERPORT_SDK_KEY` in `frontend/.env.local`. If it's off, skip the step marked below. Check once that clicking an item in the list jumps to its tag on Harwin Plaza II.
- **Rehearse the last two clicks once** (then restore). Check that excluding a building and pressing Approve work from the state the 50% slider leaves.

## Script

| Time | On screen | Do | Say |
|---|---|---|---|
| **0:00–0:15** | Goal form | Leave the goal at **40%** (don't change it). Submit. | ⚠ "One goal: cut this **7-building** Houston office portfolio's carbon by 40%. No chatbot; the agents build the screen." |
| **0:15–0:45** | Survey feed (replay of `warm_full`) | ⚠ Point at **Brookhollow Two**, then **CityNorth 6** | ⚠ "An AI investigator decides what data to pull for each building. Brookhollow Two read its roof as clear, inspected the interior and stopped: *'finished: more evidence won't change an upgrade, given roof flat, light; usable roof 75%'*. CityNorth 6 saw partial shading, so it *'pulled wider Vexcel context (321 m): to check shading'*, re-read the roof, then pulled its Matterport scan. Every building took a different path, and every line is written by code from what a tool returned." |
| | ⚠ End of the feed | Let it run to "re-plan: 7900 Fannin excluded" | ⚠ "We surveyed eight; the portfolio is the seven whose interiors the agent inspected." (The feed is the recorded 8-building survey: it shows "8 of 8" and 7900 Fannin's lines before the re-plan. Don't point at them.) |
| | *(optional, 5 s)* Research line (separate replay, `end_use_research`) | Point at the verify line | "A research agent found the EIA's official end-use table and checked every number verbatim: *20 of 20*. We don't show those shares; the product shows only what we observed." |
| **0:45–1:15** | Open **Harwin Plaza II** | Click the building | "Here's its Matterport 3D tour. Matterport labels rooms in homes, not offices, so our agent labelled them: **private office, corridor + private offices, private office**, all verified." |
| | 3D tags: **only if `VITE_EMISSIONS_3D` is on** | In the list beside the tour, click a fluorescent fixture: the tour jumps to its tag. Click the tag | ⚠ "Every tag is equipment the verifier confirmed: here, **5**: three fluorescent fixtures and two air diffusers. Click one and you get the claim, the verifier's result and the panorama it was seen in. **23 tags across all 7 buildings.** One building shows lighting only, because the verifier rejected its HVAC claim." |
| | Activity feed / evidence | Point at the send-back | "The verifier pushed back: *'Is there a photo clearly showing the wall-mounted thermostat?'* The inspector looked again, dropped the thermostat, kept the ceiling diffusers, and that was verified. Only verified claims get priced." |
| **1:15–1:30** | Plan at 40% | Back to the portfolio | ⚠ "The plan: **19 upgrades**, **3,440 t/yr** against **3,123** needed, a **0.88** chance of hitting the target, **$15.58M** upfront. Rooftop solar pays for itself; the rest is the cheapest verified path to 40%." |
| **1:30–1:42** | Slider to **50%** → target-gap view | Drag the target to 50 | ⚠ "Push to 50%: what roofs and interiors can verify tops out at **45%**, so the agents switch to the target-gap view and show the cheapest extra cuts." *(Point at the shortfall; don't read a number aloud: 50% isn't in PITCH-FACTS.)* |
| **1:42–1:52** | Exclude a building | ⚠ Exclude one building in 3D (not 7900 Fannin: it's already shown as excluded) | "Take a building out and the plan re-prices. Same agents, new layout." |
| **1:52–2:00** | Approve | Press Approve | "Approve, and financing is set up for the plan the owner just shaped." |

## Don't say

- **"It makes money"** at 40%. ⚠ Expected NPV is −$2.85M and the probability of loss is 0.82. Say instead: "solar pays for itself; the rest is the cheapest verified path."
- **"It can reach 60%"**, or 50%. ⚠ The ceiling is 45%.
- ⚠ **"8 buildings"** for the portfolio. It's 7. Say "we surveyed eight" only to explain the feed.
- ⚠ **Anything about 7900 Fannin** beyond "surveyed, not in the portfolio".
- **Any end-use share or tonnes by end use.** They aren't shown on screen.
- **That the 3D tags are in the app**, if `VITE_EMISSIONS_3D` is off.
- **"27" tags.** 27 is the data count; the screen shows **23** (lighting and air diffusers only).
- **Model-written reasons.** Quote the feed lines exactly as shown; they're composed by code.
- ⚠ **The memo's prose as fact.** Quote its numbers only; its wording ("personally inspected on site", "regulatory mandates") isn't backed by a source.
- ⚠ **The old numbers:** 23 upgrades, 3,859 t/yr vs 3,480, p(hit) 0.89, $17.52M, −$3.29M, ceiling 44%, 78 claims / 72 verified (8 buildings). Older still: 22 upgrades, 4,119 t/yr, p(hit) 0.81, $24.75M, 46 claims / 45 verified. The current ones are 19, 3,440 vs 3,123, 0.88, $15.58M, −$2.85M, 45%, 73 claims / 67 verified.
- **"3D mesh".** It's Matterport's Showcase tour; the MatterPak mesh was unavailable.
- **The 50% shortfall as a number.** It isn't in PITCH-FACTS.
