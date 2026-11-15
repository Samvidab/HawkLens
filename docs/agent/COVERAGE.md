# Coverage: what we pulled for each building, and what we couldn't

The final run `warm_full` (live, Vertex AI) and its offline replay `ro_investigator` (`CACHE_MODE=read_only`) give identical results. Paths are under `backend/`. Per building, the sources are:
- **Investigator steps:** `data/buildings/<id>/investigation.json`
- **Claims:** `verification.json`
- **Interior:** `interior.json`
- **3D positions:** `emissions_3d.json` (branch `emissions-3d`)

`data/` isn't in git (except `portfolio.json`); regenerate it with `CACHE_MODE=read_write python scripts/warm_cache.py`.

## Summary

| Building (built) | CoStar record | Vexcel aerial | Matterport interior | Investigator calls | Claims: verified / unverified / rejected | Rooms labelled | 3D tags on screen (verified positions in the data) |
|---|---|---|---|---|---|---|---|
| Paragon Center I (1984) | ✓ (+ detail pull) | ✓ overhead + wider context | ✓ scan `FTkFHSZ4isL` | 8 (call limit) | 9 / 1 / 0 | 2 | 3 (4) |
| Southwest Center (1984) | ✓ (+ detail pull) | ✓ overhead | ✓ scan `BfYuPVALqi5` | 7 | 10 / 1 / 1 | 4 | 2 (2), lighting only |
| CityNorth 6 (1987) | ✓ (+ detail pull) | ✓ overhead + wider context | ✓ scan `qcdyTgY98qu` | 8 (call limit) | 9 / 0 / 0 | 1 | 2 (5) |
| Denmark House (1982) | ✓ (+ detail pull) | ✓ overhead | ✓ scan `4z2y8ayqrWs` | 7 | 9 / 1 / 0 | 2 | 4 (4) |
| Harwin Plaza II (1983, hero) | ✓ | ✓ overhead | ✓ scan `hu9LX64osUN` | 6 | 10 / 1 / 0 | 3 | 5 (5) |
| Brookhollow Two (1972) | ✓ | ✓ overhead | ✓ scan `BfjYay5KMPo` | 6 | 12 / 0 / 0 | 4 | 2 (2) |
| Legacy Pointe (1975) | ✓ (+ detail pull) | ✓ overhead | ✓ scan `FNC3RNdVtoP` | 7 | 8 / 1 / 0 | 1 | 5 (5) |
| 7900 Fannin (2004) | ✓ | ✓ overhead | listed only, **not inspected** (investigator's choice) | 4 | 5 / 0 / 0 | 0 | 0 (none, "unknown") |
| **Total** | 8 of 8 | 8 of 8 (wider context on 2) | 7 of 8 inspected | 53 | **72 / 5 / 1 (78)** | **17** | **23 on 7 buildings** (27) |

3D tags are Lane B's on-screen count (Lane B's Playwright report `frontend/e2e/screens/co2-tags-report.json` (gitignored; `npx playwright test -c playwright.emissions.config.js`), from `GET /co2_equipment/{building_id}`): lighting fixtures and air diffusers only. The 4 verified HVAC pins that aren't air diffusers aren't tagged: Paragon Center I's thermostat, and CityNorth 6's exposed ductwork (2) and exposed VAV box and ductwork (1).

"CoStar record ✓" means the records agent read the building's kit record every time. "+ detail pull" means the investigator also called `get_costar_record` for more fields. All 8 buildings' Matterport tours are public (`tour.json`, branch `emissions-3d`).

## Per building: investigator sequence (feed lines as shown), unknowns and reasons

Each feed line is composed by code from what the tool returned; none is written by the model (`tests/test_investigator.py::test_nothing_shown_is_invented`). No tool failed or came back empty in this run: no step result is "unknown".

**Paragon Center I**
1. read CoStar record: for record details, given built 1984; 8 stories; 3 scans linked
2. inspected roof: for solar, given built 1984
3. pulled wider Vexcel context (302 m): to check shading, given shading partial
4. re-inspected roof with context: to check shading, given shading partial
5. found 3 scans with panoramas: for interior evidence, given built 1984
6. listed 9 rooms, 25 panoramas: for interior evidence, given 3 scans with panoramas
7. inspected interior (5 panoramas): for LED evidence, given built 1984
8. labelled 2 rooms: for room use, given built 1984; 3 scans with panoramas; scan has 9 rooms

Unknowns:
- **Window type: unknown, unverified.** The verifier noted "nothing observed to verify". It also sent this claim back once, asking for a close-up of the glass edge to verify double-pane glazing.

**Southwest Center**
1. read CoStar record: for record details, given built 1984; 8 stories; 5 scans linked
2. inspected roof: for solar, given built 1984; 8 stories
3. found 4 scans with panoramas: for interior evidence, given built 1984
4. listed 7 rooms, 11 panoramas: for interior evidence, given 5 scans linked
5. inspected interior (5 panoramas): for LED evidence, given built 1984
6. labelled 4 rooms: for room use, given built 1984; 5 scans linked; lighting fluorescent
7. finished: more evidence won't change an upgrade, given built 1984; roof flat, light

Unknowns:
- **HVAC ("thermostat, vav_diffuser") rejected.** The verifier's note: "The marked region on the wall is empty wall space and does not show a wall thermostat in a plastic lock box." So no HVAC positions, and the 3D view shows lighting only.
- **Window type: unknown, unverified.**

**CityNorth 6**
1. read CoStar record: for record details, given built 1987; 14 stories; 4 scans linked
2. inspected roof: for solar, given built 1987; 14 stories
3. pulled wider Vexcel context (321 m): to check shading, given shading partial
4. re-inspected roof with context: to check shading, given shading partial
5. found 4 scans with panoramas: for interior evidence, given built 1987
6. listed 19 rooms, 27 panoramas: for interior evidence, given 4 scans with panoramas
7. inspected interior (5 panoramas): for LED evidence, given 4 scans with panoramas
8. labelled 1 room: for room use, given 4 scans with panoramas; scan has 19 rooms

Unknowns: none. With wider context, the usable roof went from 0.75 to 0.70.

**Denmark House**
1. read CoStar record: for record details, given built 1982; 4 stories; 7 scans linked
2. inspected roof: for solar, given built 1982; 4 stories
3. found 4 scans with panoramas: for interior evidence, given built 1982
4. listed 2 rooms, 25 panoramas: for interior evidence, given 4 scans with panoramas
5. inspected interior (5 panoramas): for LED evidence, given built 1982
6. labelled 2 rooms: for room use, given 4 scans with panoramas; scan has 2 rooms
7. finished: more evidence won't change an upgrade, given lighting fluorescent

Unknowns:
- **Window type: unknown, unverified.**

**Harwin Plaza II (hero)**
1. inspected roof: for solar, given built 1983; 3 stories
2. found 4 scans with panoramas: for interior evidence, given built 1983
3. listed 3 rooms, 17 panoramas: for interior evidence, given built 1983; 10 scans linked
4. inspected interior (5 panoramas): for LED evidence, given built 1983; 10 scans linked
5. labelled 3 rooms: for room use, given built 1983; lighting fluorescent
6. finished: more evidence won't change an upgrade, given built 1983; 3 stories

Unknowns:
- **Window type: unknown, unverified.** The HVAC claim was sent back ("Is there a photo clearly showing the wall-mounted thermostat?"), re-checked to `vav_diffuser`, and verified.

**Brookhollow Two**
1. inspected roof: for solar, given built 1972; 6 stories
2. found 3 scans with panoramas: for interior evidence, given built 1972; 6 stories
3. listed 30 rooms, 45 panoramas: for interior evidence, given 3 scans with panoramas
4. inspected interior (5 panoramas): for LED evidence, given built 1972
5. labelled 4 rooms: for room use, given built 1972; 3 scans with panoramas
6. finished: more evidence won't change an upgrade, given roof flat, light; usable roof 75%

Unknowns: none. The interior read windows as "single"; that claim is verified.

**Legacy Pointe**
1. read CoStar record: for record details, given built 1975; 2 stories; 4 scans linked
2. inspected roof: for solar, given built 1975; 2 stories
3. found 4 scans with panoramas: for interior evidence, given built 1975
4. listed 1 room, 20 panoramas: for interior evidence, given 4 scans with panoramas
5. inspected interior (5 panoramas): for LED evidence, given built 1975; 4 scans linked
6. labelled 1 room: for room use, given built 1975; 4 scans linked; lighting fluorescent
7. finished: more evidence won't change an upgrade, given roof flat, light; usable roof 70%

Unknowns:
- **Window type: unknown, unverified.**
- The building's other linked scans include a parking garage, which the investigator is told not to use for office lighting or HVAC.

**7900 Fannin**
1. inspected roof: for solar, given built 2004; 4 stories; 1 scan linked
2. found 1 scan with panoramas: for interior evidence, given 1 scan linked
3. listed 1 room, 37 panoramas: for interior evidence, given 1 scan with panoramas
4. finished: more evidence won't change an upgrade, given built 2004; 1 scan linked

Unknowns:
- **No interior claims, so no lighting or HVAC evidence and no 3D positions.** The investigator chose not to inspect the scan.
- **Its LED retrofit stays "assumed"** (`feasibility.json`), not observed.

## Gaps that apply to every building

- **Facades and windows:** we had no oblique (side-on) Vexcel imagery, so no facade claims and no window upgrades. Window type from panoramas is "unknown" on 5 buildings.
- **Mesh:** Matterport reports every portfolio model's MatterPak as "unlocked" but its files as "unavailable", so we show the Showcase tour instead of a downloaded mesh.
- **Footprint:** CoStar records carry no building footprint, so roof area is estimated from the typical floor plate (`footprint_source: "estimated"` in `profile.json`).
- **CoStar photos:** the CDN returns 403, and we skipped them by decision rather than bypass it. Vexcel covers the aerials.
- **Interior scans are tenant suites**, not whole floors. The hero scan covers 0.97% of the building (`interior_scan.json`), so interiors are evidence, not measurements.

## CoStar track rules and criteria, and the file that proves each

| Rule or criterion | Proof |
|---|---|
| AI at the centre: the agent decides which data to pull, in what order, and when to stop | `backend/app/agents/investigator.py`; `data/buildings/*/investigation.json` (8 different sequences) |
| Pulls from 2–3 data layers (CoStar records, Vexcel aerials, Matterport 3D) | `backend/app/adapters/costar.py`, `vexcel.py`, `matterport.py`; the summary table above |
| Deciding and acting: the verifier sends doubtful claims back, and only verified evidence is priced | `backend/app/agents/verifier.py`; `data/buildings/*/verification_log.json`; `feasibility.json` (`include_in_optimizer`) |
| Composes the UI from a fixed widget set (no chatbot) | `backend/app/widgets/registry.py`; `data/runs/warm_full/state.json` (layout) |
| Spatial and visual understanding: boxes on images, pins at 3D scan positions | `backend/app/agents/aerial.py` (marks); `data/buildings/*/interior.json` (`pins`); `emissions_3d.json` (branch `emissions-3d`) |
| Quickstart problems #1 (understand commercial spaces) and #3 (agentic annotation): commercial room labels | `backend/app/agents/interior.py` (`label_rooms`); `data/buildings/*/rooms.json` (17 rooms, all verified) |
| Nothing shown is invented; failures show "unknown" | `backend/tests/test_investigator.py::test_nothing_shown_is_invented`; `backend/app/guardrails.py` |
| Kit data is read locally and streamed, never copied into the repo | `backend/app/adapters/costar.py` (reads `$COSTAR_KIT_DIR/data/commercial-property.jsonl` line by line); no kit files in `git ls-files` |
| Keys stay out of code and git | `.gitignore` (`.env`, `backend/cache/`, `backend/data/*`) |
| No writes to CoStar's Matterport account | `backend/app/adapters/matterport.py` (queries only; no GraphQL `mutation`) |
| CDN 403 respected, not bypassed | `backend/app/adapters/README.md` ("⛔ 403; skipped by decision") |
| Runs offline during judging | `backend/app/adapters/cache.py` (`CACHE_MODE=read_only`); `data/runs/ro_investigator/` (replay identical to the live run) |
