# Pitch facts (agent + data side)

Every number or claim we say on stage, with the file it comes from. If a number isn't here, don't say it.

**⚠ = changed for the 7-building demo portfolio** (7900 Fannin dropped). The previous version of this file (commit `4fa6f2f`, plan `91235cb8b3dd`) priced 8 buildings; the old value is given as "was …". Nothing was re-surveyed and no investigator ran again: the 7 buildings' surveys are the same records from the live warm-up.

**Source runs.**
- **Live warm-up (the survey):** `warm_full`, through Vertex AI on 2026-11-14, with the investigator agent on (`AGENTIC_SURVEY`, default on) and the final CVaR engine. It surveyed all 8 buildings, 7900 Fannin included.
- ⚠ **Demo plan (the 7-building re-price, `scripts/demo_plan.py`):** on run `warm_full`, a `goal` action for the 7 buildings at 40% and `risk_lambda` 0.2, then `exclude_building` 7900 Fannin, priced by the live engine; then the memo, generated once with `CACHE_MODE=read_write`. Result: plan `5e46a8e9d761`, written to `data/plans/current.json`; memo `data/memo/5e46a8e9d761.md`. The `warm_full` feed now ends with these lines: "Plan: price 7 buildings at 40% target" → "re-plan: 7900 Fannin excluded" → "optimize: 40% target, p(hit) 0.88" → "investment memo written".
- ⚠ **Offline replay:** `ro_seven`, the same actions with `CACHE_MODE=read_only`. It gave the same plan, the same memo (byte for byte) and the same widgets, with no cache misses; only the run ID and timestamps differ. (The earlier full replay `ro_investigator` reproduced all 8 investigators' tool sequences and feed lines and both send-backs.)

Paths are under `backend/`. `data/` and `cache/` are not in git (except `data/portfolio.json`); regenerate them with `CACHE_MODE=read_write python scripts/warm_cache.py`.

⚠ **Why price on 7, not exclude from 8.** The engine's `exclusions` keep an excluded building in the target's denominator. Excluding 7900 Fannin from the 8-building plan would mean 40% of the 8-building baseline, which the 7 buildings only just reach (p(hit) 0.50, below the engine's 0.80 floor). The demo plan sets the goal to the 7 buildings, so 40% means 40% of the 7 buildings' own baseline, and marks 7900 Fannin as excluded so the portfolio 3D view marks it as excluded (`excluded: true`).

**Nothing shown is invented.** Gemini writes no text that appears in the feed. It returns a tool, one of nine fixed purposes, and the IDs of facts that earlier tools returned. Code composes each feed line after the tool has run, from what it actually returned. A tool that fails or returns nothing shows "unknown". Each step's trace in `investigation.json` records the line shown and the facts it quoted. `tests/test_investigator.py::test_nothing_shown_is_invented` enforces this, and all ⚠ **49** steps on the 7 buildings (was 53 on 8) pass the same check. So **only quote the feed lines below**.

## The investigator: AI that decides what data to pull

For each building, a Gemini agent sees the owner's goal, the CoStar record and the facts established so far. It chooses one tool call at a time: CoStar record, Vexcel overhead, wider Vexcel context, Matterport scans, rooms, panoramas, roof inspection, interior inspection, room labels, or finish. It gets at most 8 calls, at temperature 0. Sources: `data/buildings/<id>/investigation.json`, the `Investigator` events in `data/runs/warm_full/events.jsonl`, and `data/runs/warm_full/tool_sequences.json`.

| Building (built) | Sequence (the feed shows each step as "what the tool returned: purpose, given facts") | What it shows |
|---|---|---|
| **Brookhollow Two** (1972) | roof → scans → listed 30 rooms, 45 panoramas → interior → labelled 4 rooms → **"finished: more evidence won't change an upgrade, given roof flat, light; usable roof 75%"** | ⚠ The stop example (was 7900 Fannin): a clear roof, so it **stopped after 6 calls** and pulled no wider context |
| **CityNorth 6** (1987) | CoStar record → inspected roof → **"pulled wider Vexcel context (321 m): to check shading, given shading partial"** → re-inspected roof with context → scans → 19 rooms → interior → labelled 1 room → call limit | Extra evidence because shading was unclear; the usable roof went from 0.75 to 0.70 and solar from 186 to 174 kW |
| **Paragon Center I** (1984) | CoStar record → roof → **wider context (302 m), "given shading partial"** → re-inspected roof → scans → 9 rooms → interior → labelled 2 rooms → call limit | Checked shading with the neighbours; the reading held at 0.75 |
| **Harwin Plaza II** (1983, hero) | roof → scans → listed 3 rooms, 17 panoramas → interior (5 panoramas) → **labelled 3 rooms** → finished | Interior and room labels for the 3D tour; no wider context; 6 calls |
| **Legacy Pointe** (1975) | CoStar record → roof → scans → listed 1 room, 20 panoramas (office suite, not the garage scan) → interior → labelled 1 room → finished | No wider context |
| **Denmark House** (1982) | CoStar record → roof → scans → rooms → interior → labelled 2 rooms → finished | No wider context |
| **Southwest Center** (1984) | CoStar record → roof → scans → rooms → interior → labelled 4 rooms → finished | No wider context |

Totals: ⚠ **7 different sequences** (was 8), 6 to 8 calls per building (was 4 to 8). Wider context was pulled on 2 buildings, both after a "shading partial" reading. ⚠ The interior was inspected on all 7 (was 7 of 8). If the investigator fails, the fixed pipeline runs instead (`graph.inspect_node`).

⚠ **7900 Fannin is out of the demo portfolio, but its survey is still in the replayed feed.** `warm_full` is the recorded 8-building survey, so its lines include "Survey up to 4 of 8 Houston buildings concurrently", 7900 Fannin's investigator lines (it listed its scan and stopped without inspecting the interior) and "Survey complete: 8 of 8 buildings, 23 feasible upgrades", followed by the re-plan to 7. We didn't edit the recording. If asked: "we surveyed eight; the demo portfolio is the seven whose interiors the agent inspected."

## 3D: verified CO₂ tags in the tour (branch `emissions-3d`, flag `VITE_EMISSIONS_3D`)

| Say | Value | Source |
|---|---|---|
| Tags on screen | **23 tags on 7 buildings** (⚠ now every building in the portfolio): lighting fixtures and air diffusers only. Each tag shows "<equipment> seen (verified): CO₂ source"; a click shows the claim, the verifier's result and the panorama it was seen in | Lane B's Playwright report `frontend/e2e/screens/co2-tags-report.json` (gitignored; `npx playwright test -c playwright.emissions.config.js`), from `GET /co2_equipment/{building_id}` |
| Why not 27 | The data has 27 verified lighting/HVAC positions. Lane B tags only lighting and air diffusers, so **4 verified HVAC pins aren't tagged**: Paragon Center I's thermostat and CityNorth 6's ductwork (2) and VAV box | `data/buildings/*/emissions_3d.json` (`seen_as`); Lane B's report |
| Only verified claims are tagged | A tag appears only for a verified pin of a verified claim. It's anchored on the tour's own sweep for that panorama (matched by ID), so no coordinate is converted or guessed | `frontend/WIRING.md` (branch `emissions-3d`); `backend/app/widgets/co2_equipment.py` |
| **Southwest Center: lighting only** | Its HVAC claim was **rejected** by the verifier: "The marked region on the wall is empty wall space and does not show a wall thermostat in a plastic lock box." Rejected claims are never tagged | `data/buildings/239618/verification.json` (`interior.hvac`) |
| Tours | ⚠ All 7 buildings' Matterport tours are public (was "all 8"), so the tour opens on each | `data/buildings/*/tour.json` |

Per building, from Lane B's report:

| Building | Lighting tags | Air-diffuser tags | Tags on screen | Not tagged (verified HVAC pin, not a diffuser) |
|---|---|---|---|---|
| Paragon Center I | 2 | 1 | 3 | 1: thermostat |
| Southwest Center | 2 | 0 | 2 | none (its HVAC claim was rejected) |
| CityNorth 6 | 2 | 0 | 2 | 3: exposed ductwork (2), exposed VAV box and ductwork (1) |
| Denmark House | 2 | 2 | 4 | none |
| Harwin Plaza II (hero) | 3 | 2 | 5 | none |
| Brookhollow Two | 1 | 1 | 2 | none |
| Legacy Pointe | 2 | 3 | 5 | none |
| **Total** | **14** | **9** | **23 on 7 buildings** | **4** |

⚠ The 7900 Fannin row (0 tags; interior not inspected) is gone with the building.

## End-use research agent (branch `emissions-3d`)

| Say | Value | Source |
|---|---|---|
| What it did | Gemini chose the official source (EIA CBECS 2018 Table E5, row "Office"). Code fetched the PDF and cached its text. Gemini quoted the title, unit, headers, row and values. **Code verified 20 of 20 checks verbatim** against the fetched text | `backend/app/agents/end_use_research.py`; `backend/app/agents/sources/houston_office_end_use.json` (`verification`) |
| The row | `Office 227 13 23 63 2 38 1 6 4 25 52` (billion kWh of electricity); measures: electricity | same file (`row_quote`, `unit`, `measures`) |
| Scope | All U.S. office buildings: Table E5 has no office × census-region cross-tabulation, so the South region isn't broken out for offices | same file (`scope`) |
| Safety | A value that isn't in the source text is rejected and nothing is saved | `backend/tests/test_end_use_research.py::test_number_not_in_source_is_rejected` |
| **On screen** | **The shares are not shown on screen.** The 3D view shows only verified equipment tags; the shares exist only in the research files | `emissions_3d.py` (`load` reads `emissions_3d.json` only); `tests/test_emissions_3d.py::test_ui_payload_has_no_shares_and_needs_no_source` |

**Don't quote end-use shares or tonnes by end use on stage.** They aren't in the product's UI. If asked, say the research agent found and verified the EIA source, and that we chose to show only what we observed.

**Don't say "27" on stage.** That's the data count; the screen shows **23 tags**. Show the tags only with `VITE_EMISSIONS_3D` on.

## Headline: 40% target

| Say | Value | Source |
|---|---|---|
| Buildings in the portfolio | ⚠ **7** Houston offices, all 7 surveyed (was 8) | `data/plans/current.json` (`goal.building_ids`); `data/portfolio.json` |
| Portfolio floor area | ⚠ **1,537,853 sq ft** rentable (sum of RBA; was 1,713,776) | `data/portfolio.json` (`rba_sqft`) |
| Data layers per building | CoStar record + Vexcel overhead + ⚠ Matterport interior on **7 of 7** (was interior on 7 of 8) | `data/buildings/*/interior.json`, `investigation.json` |
| Claims made by the inspectors | ⚠ **73** (was 78) | `data/buildings/*/verification.json` |
| Claims verified | ⚠ **67 verified, 5 unverified, 1 rejected** (was 72 / 5 / 1). Unverified: window type "unknown" on 5 buildings. Rejected: HVAC on Southwest Center | same files |
| Send-backs | **2** (Paragon Center I, Harwin Plaza II; unchanged) | `data/runs/warm_full/events.jsonl` (`kind: send_back`); `verification_log.json` |
| Send-back texts | Harwin Plaza II: *"Is there a photo clearly showing the wall-mounted thermostat?"* · Paragon Center I: *"Can you check the window glass edge up close to verify double pane glazing?"* | `data/buildings/23551/` and `239601/verification_log.json` |
| What happened next (hero) | Inspector re-checked → `hvac vav_diffuser` (dropped the thermostat) → **verified** | `data/buildings/23551/verification.json` (`interior.hvac`) |
| Hero interior findings | Lighting fluorescent (verified), HVAC ceiling VAV diffusers (verified after the send-back), windows unknown | `data/buildings/23551/interior.json` |
| Lighting seen indoors | Fluorescent on 7 of 7 buildings, all verified, so ⚠ **every LED retrofit (7 of 7) is backed by an observed claim** (was 7 of 8; 7900 Fannin's was "assumed") | `interior.json` (`lighting_type`); `feasibility.json` |
| Room labels | **17 rooms on 7 buildings, all verified** (unchanged). Hero: **Private office** (112 sq ft) · **Corridor + private offices** (792 sq ft) · **Private office** (122 sq ft) | `data/buildings/*/interior.json` (`rooms`), `rooms.json` |
| Hero scan coverage | One suite: 1,026 sq ft scanned of a 105,717 sq ft building (0.97%) | `data/buildings/23551/interior_scan.json` |
| 3D on stage | Matterport Showcase tour of the hero suite (embedded) | `data/buildings/23551/interior_scan.json` (`showcase_url`) |
| Feasible upgrades found | ⚠ **21**: 7 rooftop solar, 7 LED retrofit, 7 heat pump (was 23) | `data/buildings/*/feasibility.json` |
| Rooftop solar sized | ⚠ **4,055 kW** across 7 roofs (was 4,514 across 8); hero 417 kW | `feasibility.json` (`rooftop_solar.size_value`) |
| Baseline emissions | ⚠ **7,807.4 t/yr** for the 7 buildings (was 8,700.5 for 8) | `data/plans/current.json` (`baseline`) |
| Upgrades in the plan | ⚠ **19 of 21**: 7 solar, 7 LED, 5 heat pump (was 23 of 23). Left out: the heat pumps at Harwin Plaza II and Brookhollow Two | `data/plans/current.json` (`selected`) |
| Carbon cut | ⚠ **3,440 t/yr** vs **3,123 t/yr** needed for 40% (was 3,859 vs 3,480) | `data/plans/current.json` |
| Chance of hitting the target | ⚠ **p(hit) 0.88**, meets the engine's 0.80 floor (`met_min_p_hit: true`; was 0.89) | `data/plans/current.json` |
| Upfront cost | ⚠ **$15.58M** ($15,576,683) (was $17.52M) | `data/plans/current.json` (`total_upfront`) |
| Expected NPV (7%) | ⚠ **−$2.85M** (was −$3.29M) | `data/plans/current.json` (`exp_npv`) |
| CVaR (worst 5%) | ⚠ **−$9.01M** (was −$10.16M) | `data/plans/current.json` (`cvar5`) |
| Probability of loss | ⚠ **0.82** (was 0.83) | `data/plans/current.json` (`p_loss`) |
| Target gap | Closed: shortfall 0. With the claim-backed upgrades held out (as if nothing were verified), the same goal is infeasible, ⚠ **2,343 t/yr short** (was 2,593; recomputation, not a recorded run) | `data/plans/current.json` |
| Upgrades that pay for themselves | ⚠ **7 of 21** have a negative cost per tonne, all rooftop solar, all in the plan (was 8 of 23) | `data/plans/current.json` (`macc.bars`) |
| Engine | Live quant engine with CVaR, `stub: false`, `risk_supported: true` | `data/plans/current.json` |
| Plan ID | ⚠ `5e46a8e9d761` (was `91235cb8b3dd`) | `data/plans/current.json` (`plan_id`) |
| Memo | ⚠ Written once and cached: `data/memo/5e46a8e9d761.md`. Approve finds it and doesn't call Gemini again | `app/agents/replan.py` (`_approve`) |
| Offline demo | Full pipeline replays from cache with no network: ⚠ **396** cached Gemini responses (was 393; +3 from the re-price layouts and the memo), including every investigator decision and the memo | `cache/gemini/`; `data/runs/ro_seven/` |

## Target sweep: 20%, 40%, 60%

⚠ The 7-building portfolio (was 8), `risk_lambda` 0.2, 7% discount rate, all 21 feasible upgrades eligible. Recompute with `CACHE_MODE=read_only ENGINE_MODE=live` by calling `pricing._price_sync` with `Goal(city="Houston", target_pct=T, risk_lambda=0.2, building_ids=<the 7>)`, `pricing.load_upgrades(<the 7>)` and exclusions `["6550930"]`.

| Target | Status | Upgrades selected | Tonnes/yr cut (needed) | Upfront | Expected NPV | CVaR 5% | p(loss) | p(hit target) | Shortfall |
|---|---|---|---|---|---|---|---|---|---|
| 20% | ok | ⚠ 6 (3 solar, 3 LED) (was 15) | ⚠ 1,720 (1,561) | ⚠ $7.34M | ⚠ **+$0.04M** (was −$0.07M) | ⚠ −$3.55M | ⚠ 0.50 | ⚠ 0.91 | none |
| **40%** | **ok** | ⚠ **19 (7 solar, 7 LED, 5 heat pump)** | ⚠ **3,440 (3,123)** | ⚠ **$15.58M** | ⚠ **−$2.85M** | ⚠ **−$9.01M** | ⚠ **0.82** | ⚠ **0.88** | **none** |
| 60% | infeasible | ⚠ 21 (everything) | ⚠ 3,545 (4,684) | ⚠ $16.24M | −$3.29M | ⚠ −$9.74M | ⚠ 0.85 | 0.00 | ⚠ **1,140 t/yr** (was 1,361) |

⚠ Plan IDs: 20% `6426313849a8`, 40% `5e46a8e9d761`, 60% `4887a0c20eca`. (The 60% row's expected NPV rounds to the same −$3.29M as the old 40% plan; that's a coincidence.)

What the table says:
- ⚠ **The ceiling is 45%** (was 44%). Every feasible upgrade together cuts 3,545 t/yr, which is 45.4% of the 7,807.4 t/yr baseline. **50% is still out of reach**, so the slider-to-50% step still shows the target-gap view.
- **The risk setting changes the plan at 20%, not at 40%.**
  - ⚠ At 20% with `risk_lambda` 0, the engine picks the 7 solar arrays alone: 1,829 t/yr, $8.51M upfront, expected NPV **+$0.11M**, CVaR −$4.09M, p(loss) 0.49, p(hit) 1.00.
  - ⚠ With 0.2 it keeps 3 arrays and adds 3 LED retrofits: expected NPV +$0.04M, but a better worst case (CVaR −$3.55M) and $1.17M less upfront.
  - At 40%, `risk_lambda` 0, 0.2 and 1.0 give the same plan.
- ⚠ **Excluding a building at 40%** (still counted in the denominator): any of 5 buildings keeps the plan feasible; excluding **CityNorth 6** or **Legacy Pointe** makes it infeasible. At 50%, every exclusion is infeasible. (Recomputation; don't quote these as numbers.)

**Don't say "it makes money" at 40%.** Expected NPV is −$2.85M and the probability of loss is 0.82. Solar pays for itself; the LED and heat-pump retrofits needed to reach 40% don't. (⚠ At 20% the expected NPV is now slightly positive, +$0.04M, but with a 0.50 probability of loss: don't call that "making money" either.)

**Don't say the plan can reach 50% or 60%.**

**Don't quote model-written reasons.** The feed lines are composed by code from tool results. Quote them as they appear.

⚠ **Don't read the memo's prose aloud as fact.** Its numbers are substituted by code from the plan, but Gemini's prose around them includes phrases like "personally inspected on site" and "impending regulatory mandates" that no source supports. Quote numbers from this file instead.

## Likely judge questions

**0. What's in the 3D view?**
Only verified equipment: 23 tags on ⚠ all 7 buildings, lighting fixtures and air diffusers, each tied to a claim the verifier accepted and the panorama it was seen in. Southwest Center shows lighting only because the verifier rejected its HVAC claim. We researched and verified an EIA end-use split too, but we don't show shares on screen.

**1. Where does the data come from, and how do the layers connect? (CoStar)**
CoStar records (from the hackathon kit) give each building's type, size, stories and year built. Vexcel gives an orthophoto of each roof (7.5 cm/px native; 6–10 cm/px as cropped for most buildings, 25 cm/px for the largest), plus a 3× wider view when the investigator asks for shading context. Matterport gives panoramas and rooms. They join on CoStar's property ID, which the kit maps to Matterport model IDs (every building in the portfolio has scans linked), and on the building's latitude and longitude, which is what Vexcel takes.

**2. Is the AI actually deciding anything, or is it a fixed pipeline? (Amazon)**
It decides. Per building, Gemini picks each tool call. ⚠ Brookhollow Two read a flat, light roof with 75% usable, inspected the interior and stopped after 6 calls. CityNorth 6 saw partial shading, pulled a wider aerial view, re-read its roof and used all 8. ⚠ The 7 buildings took 7 different paths. LangGraph runs the orchestrator, fans out 4 buildings at a time, and runs the verifier loop as a conditional edge. The investigator gets at most 8 calls at temperature 0, so a replay gives the same decisions.

**3. Can the AI make things up in the feed?**
No. Gemini picks a tool, a purpose from a fixed list and the facts it relied on, by ID. It writes no text that's shown. Code writes each feed line after the tool runs, from what the tool returned. A cited fact no tool established is dropped, and a tool that fails shows "unknown". A test enforces this, and every step of the live run passes it.

**4. Do the LLMs make up numbers?**
No. Gemini describes what it sees (roof colour, fraction of roof that's open, lighting type, room type) with confidences and boxes on the image. Code computes areas and kW, and the quant engine computes every dollar and tonne. A guardrail rejects any generated text with a number that isn't in the source data.

**5. How do you know a read is right?**
A second Gemini call, the verifier, checks every claim against its image with the inspector's marks drawn on. It verifies, rejects, or sends the claim back with a specific question, up to twice. ⚠ Across the 7 buildings, 67 of 73 claims were verified and 1 was rejected. Only upgrades backed by verified claims enter the optimizer; ⚠ without them, 40% would be 2,343 t/yr short.

**6. Show me the verifier pushing back.**
On the hero, the inspector said it saw a thermostat. The verifier sent that back: "Is there a photo clearly showing the wall-mounted thermostat?" The inspector looked again, dropped the thermostat and kept the ceiling diffusers, and that was verified. It's in the replayed feed.

**7. Matterport doesn't label commercial rooms. What did you do?**
The investigator labels rooms from each room's own panoramas, using nine commercial types, with an evidence note; the verifier checks each label. This run labelled 17 rooms on 7 buildings, all verified. Matterport often merges spaces into one "room", so a label can be "corridor + private offices". Honest caveat: these are tenant suites, not whole floors. The investigator also skips amenity scans such as garages, which don't show office lighting.

**8. Why isn't there a 3D mesh?**
For every model in our portfolio, Matterport reports the MatterPak bundle as "unlocked" but its files as "unavailable", with no download link. The mesh code and route are built and tested. On stage we embed Matterport's own 3D tour (Showcase) and pin the findings beside it.

**9. Why no window upgrades, and why can't you reach 60%?**
Window upgrades need oblique (side-on) imagery of each facade, which we didn't have, and panoramas usually can't tell single from double glazing (the verifier sent one window claim back asking for a close-up of the glass edge). So the plan is roofs and interiors only, and tops out at ⚠ 45%.

**10. How accurate are the roof areas?**
CoStar records carry no building footprint, so we estimate it as a square of the typical floor plate. On the hero that's about 20% smaller than the real roof in the image, so our solar sizes are, if anything, conservative. Where the investigator pulled wider context, it could trim the usable fraction; at CityNorth 6 it went from 0.75 to 0.70.

**11. What if the network or the model fails at the venue?**
Every external call (CoStar kit, Vexcel, Matterport, Gemini, including the investigator's decisions) goes through a disk cache. The demo runs with `CACHE_MODE=read_only`, so there are no network or model calls. If the investigator fails, the fixed pipeline runs instead. If a model call fails, the result shows "unknown", the claim stays unverified, and the run still finishes.

**12. Does the plan pay for itself? How do you handle risk?**
Not at 40%: ⚠ expected NPV is −$2.85M at 7%, with a 0.82 probability of loss. Every solar installation has a negative cost per tonne, but 40% also needs LED and heat-pump retrofits that cost money. The engine runs Monte Carlo scenarios and optimizes expected NPV plus `risk_lambda` × CVaR (the average of the worst 5%), and requires at least an 80% chance of hitting the target (⚠ here 0.88). ⚠ At 20%, raising the risk setting from 0 to 0.2 gives up $0.07M of expected NPV for a $0.54M better worst case.

**13. ⚠ Why 7 buildings, when the feed surveys 8?**
We surveyed 8. The agent chose not to inspect 7900 Fannin's interior, so its LED retrofit rested on an assumption, not an observation. The demo portfolio is the 7 with inspected interiors, and 40% is 40% of those 7 buildings' baseline.
