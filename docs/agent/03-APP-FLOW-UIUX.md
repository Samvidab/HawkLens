# RetroAlpha — App Flow & UI/UX Spec (agent side)

This spec defines how the agent drives the interface: what the owner does, what the agents do in response, and the exact layout and widget contract the frontend renders. The frontend owner builds the visuals; this role owns the **layout JSON**, **widget props**, **activity feed**, and **situation logic**.

There is no chat box anywhere. The owner sets a goal and acts on widgets; the agents re-plan and recompose.

---

## 1. Flow overview

```
[1 Goal form] ──submit──► [2 Live survey] ──agents finish──► [3 Composed workspace]
                                                               │   ▲
                                         owner action on widget│   │ new layout (< 3 s)
                                                               ▼   │
                                                         [replan + recompose]
                                                               │
                                   click building ──► [4 Building detail]
                                   approve ──► [5 Approve confirm] ──yes──► [6 Executed + memo]
```

## 2. Screens and what the agent does

### 2.1 Goal form
| Field | Type | Default |
|---|---|---|
| City | Houston / Los Angeles | demo city |
| Portfolio | preselected 6–10 buildings (checkbox list from `/portfolio`) | all |
| CO₂ target | slider 0–80 % | 40 % |
| Budget | USD, optional | blank |
| Risk appetite | slider Low ↔ High → λ | middle |

Submit → `POST /run` → `run_id` → open SSE `/events/{run_id}` → go to Live survey.

### 2.2 Live survey
- Left: **activity feed** streaming events.
- Center: **portfolio 3D view** — buildings appear grey, turn colored as each survey completes.
- Right: per-building status chips: `queued → fetching → inspecting → verifying → done`.
- When the orchestrator emits `kind=done`, frontend calls `GET /state/{run_id}` and renders `layout`.

### 2.3 Composed workspace
Rendered exactly from `layout.json`. Typical first layout (situation `portfolio_overview`):
1. target_control
2. portfolio_3d
3. abatement_curve
4. plan_table
5. risk_histogram
6. financing_card
7. activity_feed (collapsed side panel, always present)

### 2.4 Building detail
Opened by clicking a building in 3D, a plan row, or a curve bar (`open_building`). Composer returns situation `building_detail`:
1. building_header (profile)
2. hero_3d (if Matterport) else portfolio_3d focused on that building
3. evidence_gallery
4. facade_compass
5. floor_plan (if Matterport)
6. upgrade_list (feasible upgrades with verify status and include toggles)
7. risk_histogram filtered to this building

### 2.5 Approve confirm
Modal from `financing_card` Approve button: shows plan total upfront, number of contractor bills, account to open. Confirm → action `approve` with `plan_id`. Cancel does nothing.

### 2.6 Executed
Composer returns situation `approved`: financing_card in executed state (Nessie IDs), memo, activity feed highlighting `act` events.

## 3. Owner actions → agent behavior

| Owner does | Action sent | Agents re-run | Visible result |
|---|---|---|---|
| Moves target slider (release) | `set_target {target_pct}` | optimize → compose | plan table, p(hit), maybe target_gap_card |
| Changes budget / risk | `set_budget` / `set_risk` | optimize → compose | plan + risk change |
| Clicks building in 3D → "Exclude" | `exclude_building {building_id}` | macc + optimize → compose | building greys out, curve and plan update |
| Toggles an upgrade off/on | `toggle_upgrade {upgrade_id, on}` | optimize → compose | — |
| Includes an unverified upgrade | `include_unverified {upgrade_id}` | optimize → compose | badge "owner-included" |
| Clicks a curve bar | `select_bar {upgrade_id}` | compose | that building's detail with the upgrade highlighted |
| Clicks a building | `open_building {building_id}` | compose | building_detail |
| Approves | `approve {plan_id}` | finance → memo → compose | executed state |

Every action also emits 1–3 activity events so the owner sees the agents respond ("Orchestrator · re-plan: Harbor Lofts excluded", "Pricing · optimize at 40% target", "Composer · showing target gap: 3,100 t short").

Debounce sliders: send on release, or at most every 400 ms.

## 4. Layout JSON contract

```json
{
  "layout_id": "lay_0042",
  "run_id": "run_7",
  "situation": "portfolio_overview",
  "focus_building_id": null,
  "generated_at": "2026-11-14T15:02:11Z",
  "widgets": [
    {
      "id": "w1",
      "type": "abatement_curve",
      "title": "Which cuts pay for themselves",
      "why": "6 of 14 upgrades have negative cost per tonne.",
      "size": "wide",
      "data_ref": "plans/current.json#/macc",
      "props": { "bars": [ ... ], "selected_upgrade_ids": [ ... ] }
    }
  ]
}
```

Rules:
- `situation` ∈ `portfolio_overview | building_detail | target_gap | verification_issue | approved`.
- `size` ∈ `full | wide | half | side`. Frontend uses a 12-column grid: full=12, wide=8, half=6, side=4.
- `why` ≤ 90 chars; any numbers in it must exist in the resolved props (guardrail).
- `props` are filled by the backend resolver from `data_ref`, never by the LLM.
- `activity_feed` is always included as `side`.
- Max 8 widgets per layout.

## 5. Widget registry (props contract)

| type | Required props | Notes |
|---|---|---|
| `target_control` | `target_pct, budget_usd, risk_lambda, p_hit_target, tonnes_needed, tonnes_planned` | Emits set_target / set_budget / set_risk |
| `portfolio_3d` | `buildings: [{building_id, name, lat, lon, footprint_wkt, height_m, roof_texture_url, color_metric, color_value, excluded, overlays: [{type: solar|cool_roof|window, polygon_wkt? , facade?}]}]`, `focus_building_id` | Height = stories × 4 m |
| `hero_3d` | `building_id, mesh_url, mtl_url, pins: [Pin], rooms?: [{room_id, type, polygon}]` | Matterport OBJ; pins colored by status |
| `abatement_curve` | `bars: [{upgrade_id, building_id, building_name, type, tonnes_per_year, cost_per_tonne, in_plan}]` | Emits select_bar |
| `plan_table` | `rows: [{upgrade_id, building_name, type, size, upfront_usd, exp_npv, cost_per_tonne, tonnes_per_year, verified}]`, `totals` | Emits toggle_upgrade |
| `risk_histogram` | `bins: [{x0, x1, count}], exp_npv, cvar5, p_loss, scope` | scope = plan or building |
| `evidence_gallery` | `items: [{image_id, url, source, orientation, marks: [Mark], claim_ids, claim_summaries, status}]` | Rejected/sent-back items first in verification_issue |
| `facade_compass` | `facades: {N,E,S,W: {glazing_ratio, window_count_est}}` | |
| `floor_plan` | `rooms: [{room_id, type, polygon, area_sqft}], pins` | From Matterport rooms |
| `upgrade_list` | `upgrades: [FeasibleUpgrade + include toggle state]` | Emits toggle_upgrade / include_unverified |
| `building_header` | `profile: BuildingProfile`, `baseline: {annual_spend_usd, tonnes_per_year}` | |
| `target_gap_card` | `shortfall_tonnes, cheapest_extra: [{upgrade_id, cost_per_tonne, tonnes_per_year}]` | |
| `financing_card` | `plan_id, total_upfront_usd, bills: [{contractor, amount}], state: proposed|executed, nessie_ids?` | Approve button |
| `memo` | `markdown` | Numbers already substituted by code |
| `activity_feed` | `run_id` | Frontend reads SSE directly |

## 6. Situation logic (composer)

The composer starts from a **template** per situation, then may drop, reorder, or add at most two widgets, and writes each `why`.

| Situation | Triggered when | Template |
|---|---|---|
| `portfolio_overview` | default after run or plan update | target_control, portfolio_3d, abatement_curve, plan_table, risk_histogram, financing_card |
| `target_gap` | optimizer says target unreachable within budget | target_control, target_gap_card, abatement_curve, plan_table, portfolio_3d |
| `verification_issue` | a selected-relevant claim is unverified/rejected after the latest run | evidence_gallery (issues first), upgrade_list, target_control, portfolio_3d |
| `building_detail` | open_building / select_bar | building_header, hero_3d or portfolio_3d, evidence_gallery, facade_compass, floor_plan?, upgrade_list, risk_histogram |
| `approved` | after finance succeeds | financing_card (executed), memo, plan_table |

Situation-specific additions:
- Large unshaded roof (usable_roof_m2 above portfolio median, shading none) → in building_detail, highlight solar overlay and put upgrade_list first among the lower widgets.
- Building has Matterport → hero_3d + floor_plan; else omit both.
- Verifier rejected a claim → evidence_gallery shows the image with the verifier note.

Composer fallback: if the LLM fails or returns invalid JSON, use the template unchanged with stock `why` strings.

## 7. Activity feed style

- One event = one fact. Format: `Agent · Building · what happened`.
- ≤ 90 characters, present tense, no filler ("Thinking…", "Great!").
- Use real names and real counts only from tool output.

Examples:
```
Orchestrator · Plan: survey 8 Houston buildings, 4 at a time
Records · Allen Center 2 · 36 stories, 1.0M sq ft, built 1980
Aerial · Allen Center 2 · roof flat, dark, no panels
Aerial · Allen Center 2 · south facade · glazing ~55%
Verifier · Allen Center 2 · sent back: "Is the north roof shaded by the tower?"
Aerial · Allen Center 2 · re-check: north 40% shaded
Site engineer · Allen Center 2 · 4 feasible upgrades (solar 310 kW)
Pricing · optimize: 40% target, p(hit) 0.82
Composer · showing target gap: 3,100 t/yr short
Finance · opened Retrofit Reserve (acct …a91f)
```
(Names and numbers above are illustrative; real ones come from data.)

Color by `kind`: plan/decide = neutral, fetch/observe = blue, verify = green, send_back = amber, error = red, act = purple.

## 8. States and edge cases

| Case | Behavior |
|---|---|
| Building has no oblique imagery | Facade widgets show "No side imagery"; window_upgrade not proposed |
| No Matterport for a building | hero_3d and floor_plan omitted; interior claims absent |
| Gemini error on a building | Event `error`; building marked partial; others continue |
| Engine not ready (stub mode) | Small "sample pricing" badge in plan_table (remove before demo) |
| Target unreachable | target_gap situation |
| Owner approves twice | Second approve returns current executed layout (idempotent) |
| Network down at judging | Cache read-only + `?replay=1` feed; no visible difference |
| Slow action (> 3 s) | Widgets keep old data with a subtle "updating" shimmer; never blank |

## 9. Demo path (2 minutes, agent moments marked ★)

1. Goal form: Houston (or LA), target 40%, submit.
2. ★ Live survey: feed scrolls, buildings light up, one **send_back** visible.
3. ★ Open hero building: real Matterport mesh, pinned verified findings, evidence gallery with roof marks.
4. Abatement curve: "every bar below zero cuts carbon and makes money."
5. Target slider to 50% → ★ composer switches to target_gap, shows cheapest extra tonnes.
6. Exclude a building in 3D → ★ re-plan in < 3 s.
7. Approve → ★ finance events, Nessie IDs, memo.
