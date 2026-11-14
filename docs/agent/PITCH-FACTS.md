# Pitch facts (agent + data side)

Every number or claim we say on stage, with the file it comes from. If a number isn't here, don't say it.

**Source run:** `warm_full`, the live run through Vertex AI on 2026-11-14, also replayed offline (`CACHE_MODE=read_only`) with identical results. Paths are under `backend/`. `data/` and `cache/` are not in git (except `data/portfolio.json`); regenerate them with `CACHE_MODE=read_write python scripts/warm_cache.py`.

## Numbers

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
| Upgrades in the plan | **22**: 8 solar, 8 LED, 6 heat pump | `data/plans/current.json` (`selected`) |
| Carbon cut | **4,119 t/yr** vs 3,907 t/yr needed for the 40% target | `data/plans/current.json` (`tonnes_per_year`, `tonnes_needed`) |
| Baseline emissions | 9,768.5 t/yr for the 8 buildings | `data/plans/current.json` (`baseline[*].tonnes_per_year`) |
| Chance of hitting the target | **p(hit) 0.81** (engine minimum 0.80) | `data/plans/current.json` (`p_hit_target`, `min_p_hit`) |
| Upfront cost | **$24.75M** ($24,750,248) | `data/plans/current.json` (`total_upfront`) |
| Target gap | Closed: shortfall 0. Before the verifier could run (all claims unverified), the same goal was infeasible, 2,006 t/yr short | `data/plans/current.json` (`status: ok`, `shortfall_tonnes`); STATUS-A.md, run `warm_full` of 18:39 UTC |
| Upgrades that pay for themselves | 8 of 23 have a negative cost per tonne, all rooftop solar | `data/plans/current.json` (`macc.bars[*].cost_per_tonne`) |
| Engine | Live quant engine, not the stub | `data/plans/current.json` (`stub: false`) |
| Offline demo | Full pipeline replays from cache, no network: 39 cached Gemini responses | `cache/gemini/` |

**Don't say "it makes money."** The plan's expected NPV is **−$9.93M** at a 7% discount rate, and its probability of loss is 0.997 (`exp_npv`, `p_loss` in `data/plans/current.json`). Solar pays for itself; the LED and heat-pump upgrades needed to reach 40% don't. The honest line is: "the cheapest path to the target, and the solar part pays for itself."

**Don't say the risk slider changes the plan.** The live engine reports `risk_supported: false`.

## Likely judge questions

**1. Where does the data come from, and how do the layers connect? (CoStar)**
CoStar records (from the hackathon kit) give each building's type, size, stories and year built. Vexcel gives an orthophoto of each roof (7.5 cm/px native; 6–10 cm/px as cropped for most buildings, 25 cm/px for the largest). Matterport gives panoramas and rooms of the hero building. They join on CoStar's property ID, which the kit maps to Matterport model IDs, and on the building's latitude and longitude, which is what Vexcel takes.

**2. Do the LLMs make up numbers?**
No. Gemini only describes what it sees: roof colour, the fraction of the roof that's open, lighting type, room type, plus confidences and boxes on the image. Code computes areas and kW, the quant engine computes every dollar and tonne, and a guardrail rejects any text with a number that isn't in the source data.

**3. How do you know a roof read is right?**
A second Gemini call, the verifier, checks every claim against its image with the inspector's marks drawn on. It verifies, rejects, or sends the claim back with a specific question, up to twice. In this run 45 of 46 claims were verified. An upgrade only goes into the optimizer if the claims behind it are verified.

**4. Show me the verifier pushing back.**
On the hero, the inspector said it saw a thermostat. The verifier sent that back: "Is there a photo clearly showing the wall-mounted thermostat?" The inspector looked again, dropped the thermostat and kept the ceiling diffusers, and that was verified. It's in the replayed feed.

**5. Matterport doesn't label commercial rooms. What did you do?**
The interior agent labels each room from that room's own panoramas, using nine commercial types, with a short evidence note; the verifier checks each label. On the hero: private office, corridor + private offices, private office, all verified. Honest caveat: it's 3 rooms. On the first pass the big "room" came back as just "corridor". A human look showed Matterport had merged a hallway with the offices off it, so we now show the agent more panoramas for big rooms and let it report merged spaces.

**6. Why isn't there a 3D mesh?**
For every model in our portfolio (37), Matterport reports the MatterPak bundle as "unlocked" but its files as "unavailable", with no download link. The mesh code and route are built and tested. On stage we embed Matterport's own 3D tour (Showcase) and pin the findings beside it.

**7. Why no window upgrades?**
Window upgrades need oblique (side-on) imagery of each facade. We only had Vexcel's overhead documentation, so facades aren't inspected and window upgrades are never proposed. The plan is roofs and interiors only.

**8. How accurate are the roof areas?**
CoStar records carry no building footprint, so we estimate it as a square of the typical floor plate. On the hero that's about 20% smaller than the real roof in the image, so our solar sizes are, if anything, conservative.

**9. Is this a real multi-step agent, or a pipeline? (Amazon)**
LangGraph: an orchestrator plans, fans out one survey per building (4 at a time), and each survey is a subgraph (records → aerial ∥ interior → site engineer → verifier loop). The loop is a real conditional edge: doubt sends a claim back to the inspector, who answers the verifier's question. Owner actions (exclude a building, move the target) go to a re-plan router that re-prices and re-composes the layout. There's no chatbot; the output is a layout of widgets.

**10. What does it cost to run, and what if the network or the model fails at the venue?**
Every external call (CoStar kit, Vexcel, Matterport, Gemini) goes through a disk cache. The demo runs with `CACHE_MODE=read_only`, so there are no network calls and no model calls. If a model call fails live, the claim stays unverified and the run still finishes; it never stops halfway.

**11. Does the plan pay for itself?**
Not overall: expected NPV is −$9.9M at 7%. Every solar installation has a negative cost per tonne, but hitting 40% also needs LED and heat-pump retrofits that cost money. The point is the *cheapest verified* path to the target, and the owner can lower the target or exclude buildings and watch the plan re-price.

**12. Why only one hero building indoors?**
Interior inspection is the most expensive step (many images per room), and the hero's Matterport scans are individual suites, not whole floors. The hero scan covers 0.97% of the building, so we use it for evidence, room labels and lighting/HVAC type, not to re-measure the building.
