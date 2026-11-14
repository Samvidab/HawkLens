# Pitch facts (agent + data side)

Every number or claim we say on stage, with the file it comes from. If a number isn't here, don't say it.

**Source runs.**
- **Live warm-up:** `warm_full`, through Vertex AI on 2026-11-14, with the **investigator agent** on (`AGENTIC_SURVEY`, default on) and the final CVaR engine.
- **Offline replay:** `ro_investigator`, with `CACHE_MODE=read_only`, a 40% target and `risk_lambda` 0.2. It reproduced all 8 investigators' tool sequences, the 3 send-backs and the same plan numbers, ending in "Workspace ready".

Paths are under `backend/`. `data/` and `cache/` are not in git (except `data/portfolio.json`); regenerate them with `CACHE_MODE=read_write python scripts/warm_cache.py`.

**⚠ = changed from the previous version of this file** (commit `667f7b0`: fixed survey pipeline, plan `64f6562caa73`). Most survey numbers changed because the investigator now inspects interiors on 7 buildings, not only the hero, and pulls wider aerial context where it sees shading. Use only the new values on stage.

## The investigator: AI that decides what data to pull (new)

For each building, a Gemini agent sees the owner's goal and the CoStar record. It then chooses one tool call at a time, with a reason: CoStar record, Vexcel overhead, wider Vexcel context, Matterport scans, rooms, panoramas, roof inspection, interior inspection, room labels, or finish. It gets at most 8 calls, at temperature 0, and every reason appears in the activity feed. Source: `data/buildings/<id>/investigation.json` (the steps with reasons and results), the `Investigator` events in `data/runs/warm_full/events.jsonl`, and `data/runs/warm_full/tool_sequences.json`.

| Building (built) | Tool sequence (feed reasons) | What it shows |
|---|---|---|
| **7900 Fannin** (2004) | inspect roof → **finish: "newer building, interior won't change decisions"** | Decided **not** to pull interior or wider context |
| **Legacy Pointe** (1975) | CoStar record → roof → scans → rooms → interior → **interior again ("windows unknown, inspect more panoramas")** → **wider context** → **roof again** → call limit | Pulled extra evidence twice. Wider context cut the usable roof from 0.70 to 0.65, so its solar went from 2,564 to 2,380 kW |
| **CityNorth 6** (1987) | scans ("built in 1987, original lighting likely") → rooms → interior → roof → **wider context ("roof shading partial, need wider context")** → roof again → label 1 room → finish | Wider context after a partial-shading read; usable roof 0.75 → 0.70 |
| **Paragon Center I** (1984) | roof → **wider context** → roof again → scans → rooms → interior → label 2 rooms → finish | Checked shading with neighbours before trusting solar |
| **Denmark House** (1982) | scans → roof → scans → rooms → interior → **interior again ("windows unknown, inspect interior with more panoramas")** → label 2 rooms → finish | Extra panoramas because a result was unclear |
| **Harwin Plaza II** (1983, hero) | roof → scans ("checking interior for original HVAC") → rooms → interior → **interior again (more panoramas for windows)** → label 3 rooms → finish | Interior first because of the building's age; no wider context |
| **Brookhollow Two** (1972) | scans ("lighting likely original") → roof → scans → rooms → interior → label 4 rooms → finish | No wider context |
| **Southwest Center** (1984) | CoStar record ("check for renovation and scans") → roof → scans → rooms → interior → label 2 rooms → finish | No wider context |

Totals: 8 different sequences. 2 to 8 calls per building. Wider context pulled on 3 buildings. Extra panoramas after an unclear answer on 3. Interior skipped on 1 (7900 Fannin). If the investigator fails, the fixed pipeline runs instead (`graph.inspect_node`).

## Headline: 40% target

| Say | Value | Source |
|---|---|---|
| Buildings surveyed | **8** Houston offices, all 8 surveyed | `data/portfolio.json`; `data/runs/warm_full/warm_summary.json` (`full_run.buildings`) |
| Portfolio floor area | 1,713,776 sq ft rentable (sum of RBA) | `data/portfolio.json` (`rba_sqft`) |
| Data layers per building | CoStar record + Vexcel overhead (8 of 8); ⚠ Matterport interior on **7 of 8** (was the hero only), chosen by the investigator | `data/buildings/*/interior.json`, `investigation.json` |
| Claims made by the inspectors | ⚠ **75** (was 46) | `data/buildings/*/verification.json` |
| Claims verified | ⚠ **68 verified, 5 unverified, 2 rejected** (was 45 / 1 / 0). Unverified: window type "unknown" on 5 buildings. Rejected: HVAC on Harwin Plaza II and Southwest Center | same files |
| Send-backs | ⚠ **3** (was 1) | `data/runs/warm_full/events.jsonl` (`kind: send_back`); `data/buildings/*/verification_log.json` |
| Send-back texts | ⚠ Harwin Plaza II: *"Is there a VAV diffuser installed elsewhere, or are these only perforated return air grilles?"* · Paragon Center I: *"Can you check the window glass edge up close to verify double pane glazing?"* · Southwest Center: *"Can you provide a close-up photograph of the window frame edge showing the glass spacer bar?"* (the thermostat send-back is no longer in the final run) | `verification_log.json` of 23551, 239601, 239618 |
| What happened next (hero) | ⚠ The inspector re-checked and kept `vav_diffuser`; the verifier then **rejected** it: "The highlighted region contains standard acoustic ceiling tile and grid without a visible VAV diffuser or air grille." (was: re-check → verified) | `data/buildings/23551/verification.json` (`interior.hvac`) |
| Hero interior findings | Lighting fluorescent (verified). ⚠ HVAC: VAV diffuser **rejected**. Windows unknown | `data/buildings/23551/interior.json`, `verification.json` |
| Lighting seen indoors | ⚠ Fluorescent on 7 of 7 inspected buildings, all verified, so 7 of 8 LED retrofits are backed by an observed claim (7900 Fannin's stays "assumed") | `data/buildings/*/interior.json` (`lighting_type`); `feasibility.json` (`led_retrofit.verified`) |
| Room labels | ⚠ **14 rooms on 6 buildings, all verified** (was 3 on the hero). Hero unchanged: **Private office** (112 sq ft) · **Corridor + private offices** (792 sq ft) · **Private office** (122 sq ft). Others include open offices, a lobby with conference and offices off it, kitchen/break rooms, storage | `data/buildings/*/interior.json` (`rooms`), `rooms.json` |
| Hero scan coverage | One suite: 1,026 sq ft scanned of a 105,717 sq ft building (0.97%) | `data/buildings/23551/interior_scan.json` |
| 3D on stage | Matterport Showcase tour of the hero suite (embedded) | `data/buildings/23551/interior_scan.json` (`showcase_url`) |
| Feasible upgrades found | **23**: 8 rooftop solar, 8 LED retrofit, 7 heat pump | `data/buildings/*/feasibility.json` |
| Rooftop solar sized | ⚠ **4,331 kW** across 8 roofs (was 4,527); hero 417 kW (unchanged) | `data/buildings/*/feasibility.json` (`rooftop_solar.size_value`) |
| Baseline emissions | 8,700.5 t/yr for the 8 buildings | `data/plans/current.json` (`baseline[*].tonnes_per_year`) |
| Upgrades in the plan | ⚠ **21 of 23**: 8 solar, 8 LED, 5 heat pump (was 23) | `data/plans/current.json` (`selected`) |
| Carbon cut | ⚠ **3,662 t/yr** vs 3,480 t/yr needed for 40% (was 3,865) | `data/plans/current.json` (`tonnes_per_year`, `tonnes_needed`) |
| Chance of hitting the target | ⚠ **p(hit) 0.74, below the engine's 0.80 floor** (`met_min_p_hit: false`; was 0.90). See "Don't say" below | `data/plans/current.json` (`p_hit_target`, `min_p_hit`, `met_min_p_hit`) |
| Upfront cost | ⚠ **$16.41M** ($16,414,139) (was $17.55M) | `data/plans/current.json` (`total_upfront`) |
| Expected NPV (7%) | ⚠ **−$2.81M** (was −$3.29M) | `data/plans/current.json` (`exp_npv`) |
| CVaR (worst 5%) | ⚠ **−$9.21M** (was −$10.17M) | `data/plans/current.json` (`cvar5`) |
| Probability of loss | ⚠ **0.81** (was 0.83) | `data/plans/current.json` (`p_loss`) |
| Target gap | Closed on expected tonnes: shortfall 0. ⚠ With the claim-backed upgrades held out (as if nothing were verified), the same goal is infeasible, **2,593 t/yr short** (was 1,722; more upgrades are now claim-backed). This is a recomputation, not a recorded run | `data/plans/current.json` (`status: ok`, `shortfall_tonnes`) |
| Upgrades that pay for themselves | 8 of 23 have a negative cost per tonne, all rooftop solar | `data/plans/current.json` (`macc.bars[*].cost_per_tonne`) |
| Engine | Live quant engine with CVaR, `stub: false`, `risk_supported: true` | `data/plans/current.json` |
| Plan ID | ⚠ `599f9a59a42f` (was `64f6562caa73`) | `data/plans/current.json` (`plan_id`) |
| Offline demo | Full pipeline replays from cache with no network: ⚠ **224** cached Gemini responses (was 39), including every investigator decision and the memo | `cache/gemini/`; `data/runs/ro_investigator/events.jsonl` |

## Target sweep: 20%, 40%, 60%

The 8-building portfolio from the warm cache, `risk_lambda` 0.2, 7% discount rate, all 23 feasible upgrades eligible. Recompute with `CACHE_MODE=read_only ENGINE_MODE=live` by calling `pricing._price_sync` with `Goal(city="Houston", target_pct=T, risk_lambda=0.2)`. ⚠ Every row changed slightly, because the solar sizes changed.

| Target | Status | Upgrades selected | Tonnes/yr cut (needed) | Upfront | Expected NPV | CVaR 5% | p(loss) | p(hit target) | Shortfall |
|---|---|---|---|---|---|---|---|---|---|
| 20% | ok | 15 (7 solar, 8 LED) | 1,923 (1,740) | $7.18M | −$0.07M | −$3.00M | 0.54 | 0.85 | none |
| **40%** | **ok** | **21 (8 solar, 8 LED, 5 heat pump)** | **3,662 (3,480)** | **$16.41M** | **−$2.81M** | **−$9.21M** | **0.81** | **0.74** | **none** |
| 60% | infeasible | 23 (everything) | 3,776 (5,220) | $17.14M | −$3.30M | −$10.00M | 0.84 | 0.00 | **1,444 t/yr** |

⚠ Plan IDs: 20% `3087df181b07`, 40% `599f9a59a42f`, 60% `41ff92551eed` (were `796968e38e4c`, `64f6562caa73`, `2074a45919b6`).

What the table says:
- ⚠ **The ceiling is 43%** (was 44%). Every feasible upgrade together cuts 3,776 t/yr, which is 43.4% of the 8,700.5 t/yr baseline.
- **The risk setting changes the plan at 20%, not at 40%.**
  - At 20% with `risk_lambda` 0, the engine picks the 8 solar arrays alone: 1,953 t/yr, $9.10M upfront, expected NPV **+$0.11M**, CVaR −$4.26M, p(loss) 0.49, p(hit) 0.99.
  - With 0.2 it swaps one array for the 8 LED retrofits: expected NPV −$0.07M, but a better worst case (CVaR −$3.00M) and $1.91M less upfront.
  - At 40%, `risk_lambda` 0, 0.2 and 1.0 give the same plan.

**Don't say the 40% plan meets the engine's confidence bar.** Expected tonnes clear the target, but p(hit) is 0.74 and the engine's floor is 0.80 (`met_min_p_hit: false`). The engine plans for an internal 44% to get a safety margin, and 44% is now above the 43.4% ceiling, so it falls back to its 42% plan (21 upgrades). It doesn't try all 23, which would raise p(hit). We've raised this with the engine owner. Honest line: "the expected cut clears 40%, with about a three-in-four chance; the ceiling with roofs and interiors alone is 43%."

**Don't say "it makes money" at 40%.** Expected NPV is −$2.81M and the probability of loss is 0.81. Solar pays for itself; the LED and heat-pump retrofits needed to reach 40% don't.

**Don't say the plan can reach 60%.**

**Don't use the thermostat send-back.** It was in the earlier run, not this one. The final run's hero send-back is the VAV-diffuser question, and that claim ended up rejected.

## Likely judge questions

**1. Where does the data come from, and how do the layers connect? (CoStar)**
CoStar records (from the hackathon kit) give each building's type, size, stories and year built. Vexcel gives an orthophoto of each roof (7.5 cm/px native; 6–10 cm/px as cropped for most buildings, 25 cm/px for the largest), plus a 3× wider view when the investigator asks for shading context. Matterport gives panoramas and rooms. They join on CoStar's property ID, which the kit maps to Matterport model IDs (every building in the portfolio has scans linked), and on the building's latitude and longitude, which is what Vexcel takes.

**2. Is the AI actually deciding anything, or is it a fixed pipeline? (Amazon)**
It decides. Per building, Gemini picks each tool call and says why. 7900 Fannin, built 2004, stopped after the roof: "newer building, interior won't change decisions". Legacy Pointe pulled more panoramas when windows were unclear, then wider aerial context, and re-read its roof. The 8 buildings took 8 different paths. Around that, LangGraph runs the orchestrator, fans out 4 buildings at a time, and runs the verifier loop as a conditional edge. The investigator gets at most 8 calls at temperature 0, so a replay gives the same decisions.

**3. Do the LLMs make up numbers?**
No. Gemini describes what it sees (roof colour, fraction of roof that's open, lighting type, room type) with confidences and boxes on the image. Code computes areas and kW, and the quant engine computes every dollar and tonne. A guardrail rejects any generated text with a number that isn't in the source data, including the investigator's reasons.

**4. How do you know a read is right?**
A second Gemini call, the verifier, checks every claim against its image with the inspector's marks drawn on. It verifies, rejects, or sends the claim back with a specific question, up to twice. In this run 68 of 75 claims were verified and 2 were rejected. Only upgrades backed by verified claims enter the optimizer; without them, 40% would be 2,593 t/yr short.

**5. Show me the verifier pushing back.**
On the hero, the inspector reported VAV diffusers. The verifier asked: "Is there a VAV diffuser installed elsewhere, or are these only perforated return air grilles?" The inspector looked again and kept its answer. The verifier rejected it: "standard acoustic ceiling tile and grid without a visible VAV diffuser or air grille." It's in the replayed feed.

**6. Matterport doesn't label commercial rooms. What did you do?**
The investigator labels rooms from each room's own panoramas, using nine commercial types, with an evidence note; the verifier checks each label. This run labelled 14 rooms on 6 buildings, all verified. Matterport often merges spaces into one "room", so a label can be "corridor + private offices". Honest caveat: these are tenant suites, not whole floors.

**7. Why isn't there a 3D mesh?**
For every model in our portfolio, Matterport reports the MatterPak bundle as "unlocked" but its files as "unavailable", with no download link. The mesh code and route are built and tested. On stage we embed Matterport's own 3D tour (Showcase) and pin the findings beside it.

**8. Why no window upgrades, and why can't you reach 60%?**
Window upgrades need oblique (side-on) imagery of each facade, which we didn't have. The panoramas usually can't tell single from double glazing either; the verifier sent two window claims back asking for a close-up of the glass edge. So the plan is roofs and interiors only, and tops out at 43%.

**9. How accurate are the roof areas?**
CoStar records carry no building footprint, so we estimate it as a square of the typical floor plate. On the hero that's about 20% smaller than the real roof in the image, so our solar sizes are, if anything, conservative. Where the investigator pulled wider context, it trimmed the usable fraction, for example Legacy Pointe from 0.70 to 0.65.

**10. What does it cost to run, and what if the network or the model fails at the venue?**
Every external call (CoStar kit, Vexcel, Matterport, Gemini, including the investigator's decisions) goes through a disk cache. The demo runs with `CACHE_MODE=read_only`, so there are no network or model calls. If the investigator fails, the fixed pipeline runs instead. If a model call fails, the claim stays unverified and the run still finishes.

**11. Does the plan pay for itself? How do you handle risk?**
Not at 40%: expected NPV is −$2.81M at 7%, with a 0.81 probability of loss. Every solar installation has a negative cost per tonne, but 40% also needs LED and heat-pump retrofits that cost money. The engine runs Monte Carlo scenarios and optimizes expected NPV plus `risk_lambda` × CVaR (the average of the worst 5%). At 20%, raising the risk setting from 0 to 0.2 gives up $0.18M of expected NPV for a $1.26M better worst case.

**12. Why tenant suites, not whole buildings, indoors?**
The Matterport scans CoStar links are individual suites. The hero scan covers 0.97% of the building. We use interiors as evidence (lighting, HVAC, room use), not to re-measure the building, and the investigator inspects one scan per building.
