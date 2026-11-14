# Pitch facts (agent + data side)

Every number or claim we say on stage, with the file it comes from. If a number isn't here, don't say it.

**Source runs.**
- **Survey (buildings, claims, send-back, rooms):** `warm_full`, the live run through Vertex AI on 2026-11-14.
- **Plan numbers:** the final engine (with CVaR, merged from `agent` at `ea5601e`) on that same survey output. They were replayed offline with `CACHE_MODE=read_only` as run `ro_engine_final`, a 40% target and `risk_lambda` 0.2. That replay reproduced the same survey, the same send-back and "Workspace ready".

Paths are under `backend/`. `data/` and `cache/` are not in git (except `data/portfolio.json`); regenerate them with `CACHE_MODE=read_write python scripts/warm_cache.py`.

**⚠ = changed from the previous version of this file** (old engine, plan `31c0d8cb3a2e`). Use only the new values on stage.

## Headline: 40% target

| Say | Value | Source |
|---|---|---|
| Buildings surveyed | **8** Houston offices, all 8 surveyed | `data/portfolio.json` (`buildings`); `data/runs/warm_full/warm_summary.json` (`full_run.buildings`) |
| Portfolio floor area | 1,713,776 sq ft rentable (sum of RBA) | `data/portfolio.json` (`rba_sqft`) |
| Data layers per building | CoStar record + Vexcel overhead (8 of 8); Matterport interior on the hero | `data/portfolio.json` (`coverage.vexcel = "overhead"`); `data/buildings/23551/interior.json` |
| Claims made by the inspectors | **46** | `data/runs/warm_full/warm_summary.json` (`full_run.buildings[*].claims`) |
| Claims verified | **45 verified, 1 unverified, 0 rejected** | same file; the unverified one is the hero's window type ("unknown", nothing to check) |
| Send-backs | **1**, on the hero's HVAC claim | `warm_summary.json` (`full_run.send_backs`); `data/runs/warm_full/events.jsonl` (`kind: send_back`) |
| Send-back text | *"Is there a photo clearly showing the wall-mounted thermostat?"* | same |
| What happened next | Inspector re-checked → `hvac vav_diffuser` (dropped the thermostat) → verified | `warm_summary.json` (`rechecks`); `data/buildings/23551/verification.json` (`interior.hvac`: loops 1, verified) |
| Hero interior findings | Lighting fluorescent (verified), HVAC ceiling VAV diffusers (verified after the send-back), windows unknown | `data/buildings/23551/interior.json` |
| Room labels (hero scan, 3 rooms) | **Private office** (112 sq ft) · **Corridor + private offices** (792 sq ft) · **Private office** (122 sq ft), all verified | `data/buildings/23551/interior.json` (`rooms`), `data/buildings/23551/rooms.json`, `verification.json` (`interior.room.*`) |
| Hero scan coverage | One suite: 1,026 sq ft scanned of a 105,717 sq ft building (0.97%) | `data/buildings/23551/interior_scan.json` (`scanned_floor_area_sqft`, `coverage_of_rba`) |
| 3D on stage | Matterport Showcase tour of the hero suite (embedded) | `data/buildings/23551/interior_scan.json` (`showcase_url`) |
| Feasible upgrades found | **23**: 8 rooftop solar, 8 LED retrofit, 7 heat pump | `data/buildings/*/feasibility.json` |
| Rooftop solar sized | 4,527 kW across 8 roofs (hero: 417 kW) | `data/buildings/*/feasibility.json` (`rooftop_solar.size_value`) |
| Baseline emissions | ⚠ **8,700.5 t/yr** for the 8 buildings (was 9,768.5: the engine's sourced assumptions changed) | `data/plans/current.json` (`baseline[*].tonnes_per_year`) |
| Upgrades in the plan | ⚠ **23 of 23**: 8 solar, 8 LED, 7 heat pump (was 22) | `data/plans/current.json` (`selected`) |
| Carbon cut | ⚠ **3,865 t/yr** vs 3,480 t/yr needed for 40% (was 4,119 vs 3,907) | `data/plans/current.json` (`tonnes_per_year`, `tonnes_needed`) |
| Chance of hitting the target | ⚠ **p(hit) 0.90** (was 0.81). The engine requires ≥ 0.80, so it planned for an internal 44% | `data/plans/current.json` (`p_hit_target`, `min_p_hit`, `internal_target_pct`) |
| Upfront cost | ⚠ **$17.55M** ($17,550,653) (was $24.75M) | `data/plans/current.json` (`total_upfront`) |
| Expected NPV (7%) | ⚠ **−$3.29M** (was −$9.93M) | `data/plans/current.json` (`exp_npv`) |
| CVaR (worst 5%) | ⚠ **−$10.17M** (was −$16.04M) | `data/plans/current.json` (`cvar5`) |
| Probability of loss | ⚠ **0.83** (was 0.997) | `data/plans/current.json` (`p_loss`) |
| Target gap | Closed: shortfall 0. ⚠ With the claim-backed upgrades held out (8 solar + the hero's LED, i.e. as if nothing were verified), the same goal is infeasible, **1,722 t/yr short** (was 2,006, recorded under the old engine; the new figure is a recomputation, not a recorded run) | `data/plans/current.json` (`status: ok`, `shortfall_tonnes`) |
| Upgrades that pay for themselves | 8 of 23 have a negative cost per tonne, all rooftop solar | `data/plans/current.json` (`macc.bars[*].cost_per_tonne`) |
| Engine | Live quant engine with CVaR, not the stub. ⚠ `risk_supported: true` (was false) | `data/plans/current.json` (`stub: false`, `risk_supported`) |
| Plan ID | ⚠ `64f6562caa73` (was `31c0d8cb3a2e`) | `data/plans/current.json` (`plan_id`) |
| Offline demo | Full pipeline replays from cache, no network: 39 cached Gemini responses (including the investment memo for this plan) | `cache/gemini/`; `data/runs/ro_engine_final/events.jsonl` |

## Target sweep: 20%, 40%, 60% (new)

The 8-building portfolio from the warm cache, `risk_lambda` 0.2, 7% discount rate, all 23 feasible upgrades eligible. Recompute with `CACHE_MODE=read_only ENGINE_MODE=live` by calling `pricing._price_sync` with `Goal(city="Houston", target_pct=T, risk_lambda=0.2)` (plan IDs below).

| Target | Status | Upgrades selected | Tonnes/yr cut (needed) | Upfront | Expected NPV | CVaR 5% | p(loss) | p(hit target) | Shortfall |
|---|---|---|---|---|---|---|---|---|---|
| 20% | ok | 15 (7 solar, 8 LED) | 1,928 (1,740) | $7.21M | −$0.07M | −$3.01M | 0.54 | 0.86 | none |
| **40%** | **ok** | **23 (8 solar, 8 LED, 7 heat pump)** | **3,865 (3,480)** | **$17.55M** | **−$3.29M** | **−$10.17M** | **0.83** | **0.90** | **none** |
| 60% | infeasible | 23 (everything) | 3,865 (5,220) | $17.55M | −$3.29M | −$10.17M | 0.83 | 0.00 | **1,356 t/yr** |

Plan IDs: 20% `796968e38e4c`, 40% `64f6562caa73`, 60% `2074a45919b6`.

What the table says:
- **The ceiling is 44%.** Every feasible upgrade together cuts 3,865 t/yr, which is 44% of the 8,700.5 t/yr baseline. 60% can't be reached with roofs and interiors alone. The 60% row is "all upgrades, still short", and its p(hit) is 0.
- **The risk setting changes the plan at 20%, not at 40%.**
  - At 20% with `risk_lambda` 0 (expected value only), the engine picks the 8 solar arrays alone: 2,042 t/yr, $9.51M upfront, expected NPV **+$0.12M**, CVaR −$4.47M, p(loss) 0.49, p(hit) 1.00.
  - With `risk_lambda` 0.2, it swaps one solar array for the 8 LED retrofits: expected NPV −$0.07M, but a much better worst case (CVaR −$3.01M) and $2.30M less upfront.
  - At 40% every upgrade is needed, so `risk_lambda` 0, 0.2, 0.5 and 1.0 all give the same plan.

**Don't say "it makes money" at 40%.** Expected NPV is −$3.29M and the probability of loss is 0.83. Solar pays for itself; the LED and heat-pump retrofits needed to reach 40% don't. The honest line is: "the cheapest verified path to 40%, and the solar part pays for itself." If asked, the risk-neutral 20% plan (solar only) has a slightly positive expected NPV.

**Don't say the plan can reach 60%.** It tops out at 44% with what we can verify from roofs and one interior.

## Likely judge questions

**1. Where does the data come from, and how do the layers connect? (CoStar)**
CoStar records (from the hackathon kit) give each building's type, size, stories and year built. Vexcel gives an orthophoto of each roof (7.5 cm/px native; 6–10 cm/px as cropped for most buildings, 25 cm/px for the largest). Matterport gives panoramas and rooms of the hero building. They join on CoStar's property ID, which the kit maps to Matterport model IDs, and on the building's latitude and longitude, which is what Vexcel takes.

**2. Do the LLMs make up numbers?**
No. Gemini only describes what it sees: roof colour, the fraction of the roof that's open, lighting type, room type, plus confidences and boxes on the image. Code computes areas and kW, the quant engine computes every dollar and tonne, and a guardrail rejects any text with a number that isn't in the source data.

**3. How do you know a roof read is right?**
A second Gemini call, the verifier, checks every claim against its image with the inspector's marks drawn on. It verifies, rejects, or sends the claim back with a specific question, up to twice. In this run 45 of 46 claims were verified. An upgrade only goes into the optimizer if the claims behind it are verified; without the claim-backed upgrades (the 8 solar arrays and the hero's LED), 40% would be 1,722 t/yr short.

**4. Show me the verifier pushing back.**
On the hero, the inspector said it saw a thermostat. The verifier sent that back: "Is there a photo clearly showing the wall-mounted thermostat?" The inspector looked again, dropped the thermostat and kept the ceiling diffusers, and that was verified. It's in the replayed feed.

**5. Matterport doesn't label commercial rooms. What did you do?**
The interior agent labels each room from that room's own panoramas, using nine commercial types, with a short evidence note; the verifier checks each label. On the hero: private office, corridor + private offices, private office, all verified. Honest caveat: it's 3 rooms. On the first pass the big "room" came back as just "corridor". A human look showed Matterport had merged a hallway with the offices off it, so we now show the agent more panoramas for big rooms and let it report merged spaces.

**6. Why isn't there a 3D mesh?**
For every model in our portfolio (37), Matterport reports the MatterPak bundle as "unlocked" but its files as "unavailable", with no download link. The mesh code and route are built and tested. On stage we embed Matterport's own 3D tour (Showcase) and pin the findings beside it.

**7. Why no window upgrades, and why can't you reach 60%?**
Window upgrades need oblique (side-on) imagery of each facade. We only had Vexcel's overhead documentation, so facades aren't inspected and window upgrades are never proposed. That's also part of why the plan tops out at 44%: with roofs and interiors only, 60% is 1,356 t/yr short.

**8. How accurate are the roof areas?**
CoStar records carry no building footprint, so we estimate it as a square of the typical floor plate. On the hero that's about 20% smaller than the real roof in the image, so our solar sizes are, if anything, conservative.

**9. Is this a real multi-step agent, or a pipeline? (Amazon)**
LangGraph: an orchestrator plans, fans out one survey per building (4 at a time), and each survey is a subgraph (records → aerial ∥ interior → site engineer → verifier loop). The loop is a real conditional edge: doubt sends a claim back to the inspector, who answers the verifier's question. Owner actions (exclude a building, move the target or the risk setting) go to a re-plan router that re-prices and re-composes the layout. There's no chatbot; the output is a layout of widgets.

**10. What does it cost to run, and what if the network or the model fails at the venue?**
Every external call (CoStar kit, Vexcel, Matterport, Gemini) goes through a disk cache. The demo runs with `CACHE_MODE=read_only`, so there are no network calls and no model calls. If a model call fails live, the claim stays unverified and the run still finishes; it never stops halfway.

**11. Does the plan pay for itself? How do you handle risk?**
Not at 40%: expected NPV is −$3.29M at 7%, with a 0.83 probability of loss. Every solar installation has a negative cost per tonne, but 40% also needs LED and heat-pump retrofits that cost money. The engine runs Monte Carlo scenarios and optimizes expected NPV plus `risk_lambda` × CVaR (the average of the worst 5%). It also requires at least an 80% chance of actually hitting the target, which is why it plans for 44% and gets p(hit) 0.90. At 20%, raising the risk setting from 0 to 0.2 trades $0.19M of expected NPV for a $1.46M better worst case.

**12. Why only one hero building indoors?**
Interior inspection is the most expensive step (many images per room), and the hero's Matterport scans are individual suites, not whole floors. The hero scan covers 0.97% of the building, so we use it for evidence, room labels and lighting/HVAC type, not to re-measure the building.
