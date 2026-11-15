# Demo script (2 minutes)

Every number below is in `docs/agent/PITCH-FACTS.md`. If a number isn't there, don't say it.

## Before going on stage

- **Backend, offline:** `cd backend && scripts/run_server.sh demo`. This sets `CACHE_MODE=read_only`, so there are no network or model calls; a cache miss is an error, not a live call.
- **Recorded run:** `run_id` **`warm_full`** (the live warm-up; the replay `ro_investigator` is identical).
  - The frontend replays its feed at demo pace with `GET /events/warm_full?replay=1`.
  - Terminal check, about 35 s: `python scripts/replay_demo.py warm_full`.
- **Research lines:** these are a separate recorded run, `end_use_research` (5 lines, branch `emissions-3d`). Check them with `python scripts/replay_demo.py end_use_research`. They are **not** in the `warm_full` feed.
- **3D tags:** `VITE_EMISSIONS_3D` is on only if Lane B has wired `emissions_3d` into the 3D view. If it's off, skip the step marked below.
- **Rehearse the last two clicks once.** Check that excluding a building and pressing Approve work from the state the 50% slider leaves.

## Script

| Time | On screen | Do | Say |
|---|---|---|---|
| **0:00–0:15** | Goal form | Leave the goal at **40%** (don't change it). Submit. | "One goal: cut this 8-building Houston office portfolio's carbon by 40%. No chatbot; the agents build the screen." |
| **0:15–0:45** | Survey feed (replay of `warm_full`) | Point at **7900 Fannin**, then **CityNorth 6** | "An AI investigator decides what data to pull for each building. 7900 Fannin, built 2004: it read the roof, looked at the scan and stopped: *'finished: more evidence won't change an upgrade, given built 2004; 1 scan linked'*. CityNorth 6, built 1987, saw partial shading, so it *'pulled wider Vexcel context (321 m): to check shading'*, re-read the roof, then pulled its Matterport scan. Eight buildings, eight different paths, and every line is written by code from what a tool returned." |
| | *(optional, 5 s)* Research line (separate replay, `end_use_research`) | Point at the verify line | "A research agent found the EIA's official end-use table and checked every number verbatim: *20 of 20*. We don't show those shares; the product shows only what we observed." |
| **0:45–1:15** | Open **Harwin Plaza II** | Click the building | "Here's its Matterport 3D tour. Matterport labels rooms in homes, not offices, so our agent labelled them: **private office, corridor + private offices, private office**, all verified." |
| | 3D tags: **only if `VITE_EMISSIONS_3D` is on** | Point at a tag | "These tags are only verified equipment: fluorescent lighting and ceiling diffusers, each tied to the claim and the panorama it was seen in. 27 across 7 buildings. One building shows lighting only, because the verifier rejected its HVAC claim." |
| | Activity feed / evidence | Point at the send-back | "The verifier pushed back: *'Is there a photo clearly showing the wall-mounted thermostat?'* The inspector looked again, dropped the thermostat, kept the ceiling diffusers, and that was verified. Only verified claims get priced." |
| **1:15–1:30** | Plan at 40% | Back to the portfolio | "The plan: **23 upgrades**, **3,859 t/yr** against **3,480** needed, a **0.89** chance of hitting the target, **$17.52M** upfront. Rooftop solar pays for itself; the rest is the cheapest verified path to 40%." |
| **1:30–1:42** | Slider to **50%** → target-gap view | Drag the target to 50 | "Push to 50%: what roofs and interiors can verify tops out at **44%**, so the agents switch to the target-gap view and show the cheapest extra cuts." *(Point at the shortfall; don't read a number aloud: 50% isn't in PITCH-FACTS.)* |
| **1:42–1:52** | Exclude a building | Exclude one building in 3D | "Take a building out and the plan re-prices. Same agents, new layout." |
| **1:52–2:00** | Approve | Press Approve | "Approve, and financing is set up for the plan the owner just shaped." |

## Don't say

- **"It makes money"** at 40%. Expected NPV is −$3.29M and the probability of loss is 0.83. Say instead: "solar pays for itself; the rest is the cheapest verified path."
- **"It can reach 60%"**, or 50%. The ceiling is 44%.
- **Any end-use share or tonnes by end use.** They aren't shown on screen.
- **That the 3D tags are in the app**, if `VITE_EMISSIONS_3D` is off.
- **Model-written reasons.** Quote the feed lines exactly as shown; they're composed by code.
- **The old numbers:** 22 upgrades, 4,119 t/yr, p(hit) 0.81, $24.75M, 46 claims / 45 verified. The current ones are 23, 3,859, 0.89, $17.52M, 78 claims / 72 verified.
- **"3D mesh".** It's Matterport's Showcase tour; the MatterPak mesh was unavailable.
- **"Every building"** for interiors or rooms. Interiors were inspected on 7 of 8, and 17 rooms were labelled on 7 buildings.
- **The 50% shortfall as a number.** It isn't in PITCH-FACTS.
