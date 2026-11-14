# STATUS — Lane B (support), branch lane-support

## Done (all committed)
- T1.2 schemas (`app/schemas/`)
- T1.3 LLM wrapper (`app/agents/llm.py`) — unit tests + live smoke test passed (real image + toy schema, 2nd call cached) using GEMINI_MODEL_VISION=gemini-3.5-flash override; added 60 s per-call timeout and no-retry on non-transient 4xx
- T1.4 events bus + SSE router (`app/events.py`) — router not yet mounted in main.py (not my file)
- T1.7 feasibility rules (`app/rules/`)
- widgets: registry, templates, resolver (`app/widgets/`)
- T4.1 guardrails: `check_numbers`, `guarded_text`, `fill_placeholders`, `StepCounter` (`app/guardrails.py`)

- llm.py: vision falls back once to GEMINI_MODEL_VISION_FALLBACK (=gemini-3.5-flash, set in all 3 .env) on 5xx/timeout after retries; cached under primary key

- main.py: events router mounted, GET /registry, GET /portfolio (returns portfolio.json as-is)

- T2.4 engine + Nessie stubs (`integrations/engine_client.py`, `nessie_client.py`, `fixtures/engine/stub_params.json`) with contract tests. Stub engine returns the extras the quant-engine branch documents (upfront_usd, tonnes_per_year, status, p_loss, hist_bins, tonnes_needed, shortfall_tonnes, cheapest_extra, baseline()) and flags `stub: true`. Live mode imports `app.engine`. Nessie `Bill` shape is mine (TRD left it undefined); teammate to replace file.

- T2.5 pricing node (`agents/pricing.py`), composer v0 (`agents/composer.py`, portfolio_overview only), POST /compose (goal/set_target/set_budget/set_risk re-price; other actions just recompose until T3.1), GET /state/{run_id}, `storage.py` atomic writes. AC-3 path works against the stub engine: goal in -> layout JSON out (tested).

- T3.5 memo writer (`agents/memo.py`, `agents/prompts/memo.md`): Gemini fast writes placeholder-only prose (never sees figures); code substitutes; `guarded_text` rejects invented numbers, regenerates without numbers, then falls back to a template; final `check_numbers` on the substituted text; code-built appendix table; stub disclosure line. Passes the number check on 3 different plans (tests) and a live run with gemini-3.5-flash-lite. Not wired to an `approve` action yet (T3.1/T3.4). Emits kind `compose`, not `done`: the SSE live stream ends at the first `done`, so a second `done` in the same run would hide later events.

- Merged `agent` (Lane A) into lane-support. Media routes (`app/media.py`, mounted in main.py): GET /media/{image_id} via data/buildings/*/images.json (served only from inside cache/ or data/), GET /media/mesh/{model_id}/{file} from cache/media/mesh/<id>/ (obj/mtl/jpg/png only; `model.obj`/`model.mtl` alias the zip's real names so resolver URLs work).

- T3.4 finance agent (`agents/finance.py`): Nessie writes only on `approve` with plan_id == plans/current.json plan_id (else 409, nothing written). Creates Retrofit Reserve, transfers total upfront, one bill per contractor type, one `act` event per call with the ID. Idempotent by plan_id; progress persisted to data/finance/<plan_id>.json after every call so a retry resumes without double-booking. `POST /compose` `approve` runs finance -> memo (skipped if already written) -> `approved` layout; repeat approve books nothing and makes no LLM call. Tested against the Nessie stub, incl. mid-way failure. Source/customer accounts come from NESSIE_CUSTOMER_ID / NESSIE_SOURCE_ACCOUNT_ID (stub defaults only in stub mode); Nessie teammate to supply real ones for live mode.

- T3.1 replan router (`agents/replan.py`, wired into POST /compose; main.py is now thin): TRD §9 mapping implemented for all 11 action types. Owner decisions (excluded buildings/upgrades, owner_included, goal) persist in plans/current.json; view state (focus building, highlighted upgrades, issues_shown) in runs/<id>/state.json `view`. 1-3 events per action (Orchestrator `plan` + Pricing `price` + Composer `compose`); `approve` also emits the Finance `act` events + memo event (exempt from the 1-3 cap, by design). A new `goal` resets owner decisions; `open_building` with building_id null returns to the overview. Each action < 3 s with the stub engine (tested). `goal` calls a survey runner registered via `replan.register_survey_runner(fn)` when buildings lack feasibility.json (Lane A's graph can register `fn(run_id, goal, missing_ids)`); without one it emits an `error` event and prices the rest. graph.py untouched.

- T3.2 composer v1 (`agents/composer.py`, `agents/prompts/composer.md`): situation detection in code (priority approved > building_detail > verification_issue (new findings only, tracked in view.issues_shown; resolved by include/exclude/toggle-off) > target_gap > portfolio_overview). Gemini FAST (`text_json`, no images) may only drop <=2 / reorder / add <=2 from a per-situation whitelist, never drop pinned widgets, and writes `why` lines using code-filled placeholders ({{n_negative_bars}} etc.; it never sees plan figures). Anything invalid, slow (1.5 s budget; the call keeps running to warm the cache), or failing falls back to the template; each `why` is individually checked (<=90 chars, numbers explained by plan/props, known placeholders) with stock fallback. Large unshaded roof rule: upgrade_list leads the lower widgets and the solar upgrade is highlighted. Tests: scripted fixtures for all 5 situations + 14 LLM-limit/fallback cases (tests/conftest.py disables the composer LLM by default). Live check on gemini-3.5-flash-lite: valid selection in ~1.4 s, repeat calls ~0.02 s from cache.

- T4.2 prep: `scripts/replay_demo.py [run_id] [--file F] [--total 35] [--fast]` replays a recorded events.jsonl offline (no keys/cache/network) as `Agent · Building · message`, coloured by kind; auto-picks the longest run. Pacing is `app.events.pace` (weighted by kind, so send_back dwells longer; ~35 s for a realistic 30-90 event run, shorter for tiny runs), shared with `GET /events/{run_id}?replay=1`. Real-time check: 6 s target -> 6.5 s. Still to do for AC-7 (not mine/not yet possible): warm the cache with a full run, run the whole demo path with wifi off.

- Engine live mode (`integrations/engine_client.py`): `ENGINE_MODE=live` calls `app.engine.simulate/macc/optimize/set_assumption/baseline` (accepts `get_macc` as an alias for `macc`). `live_contract_drift()` (signatures vs TRD §8.1; run `python -m app.integrations.engine_client`) and `check_outputs()` (keys the widgets/finance need; pricing emits ONE `error` event "engine contract drift: ..." and carries on) catch drift at runtime. `simulate()` is skipped when upgrades, flags and assumptions are unchanged, so slider moves don't re-run the Monte Carlo. Tested against a fake engine module.

## In progress
- hero MatterPak check: waiting for Lane A to extract it (no cache/media/mesh/ in this worktree or the main checkout yet)

## Blocked / needs others
- pricing owner must match the plans/current.json shape in `app/widgets/resolver.py` docstring (incl. per-upgrade `upfront_usd`)
- aerial/interior authors must use claim field prefixes in `app/rules/feasibility.yaml`
- (model names: resolved, see below)

## Gemini model choice (resolved 2026-11-14; written to .env in support, data, and main checkouts)
VISION=`gemini-3.6-flash`, FAST=`gemini-3.5-flash-lite`. Three trials each (one image call / one tiny text call, 60-100 s cap):

| role | model | trial 1 | trial 2 | trial 3 | verdict |
|---|---|---|---|---|---|
| vision | gemini-pro-latest | 404 | - | - | not on key |
| vision | gemini-3.1-pro-preview-customtools | 404 | - | - | not on key |
| vision | gemini-3.7-flash | timeout 100 s | 503 | timeout 60 s | unreliable |
| vision | gemini-3.6-flash | 503 | ok 3.0 s | ok 18.2 s | **chosen** (llm.py retries 5xx) |
| vision | gemini-3.5-flash (extra baseline) | ok ~21 s (smoke) | - | ok 18.2 s | reliable, one tier older; fallback |
| fast | gemini-3.5-flash-lite | ok 5.4 s | ok 4.0 s | ok 0.8 s | **chosen** |
| fast | gemini-3.1-flash-lite | ok 2.4 s | timeout 100 s | ok 13.9 s | unreliable |
| fast | gemini-3.5-flash | ok 31.5 s | ok 3.2 s | ok 5.1 s | slower, variable |
Earlier: gemini-3.8-flash gave 503 / hang; gemini-3.1-pro-preview 404.
Latency is high and variable (vision 3-20 s per call); plan the demo from cache.

## Engine contract drift for the quant teammate (checked 2026-11-14 against origin/quant-engine)
**origin/quant-engine has no engine code yet** (only `app/engine/CLAUDE.md` + numpy/pulp in requirements.txt), so this compares their CLAUDE.md to TRD §8.1 and to how the agent side calls it. Re-run `python -m app.integrations.engine_client` once `app.engine` exists.
1. **Names:** PRD FR-12 says `get_macc`; TRD and their CLAUDE.md say `macc`. We call `macc` (alias `get_macc` also accepted). Nothing to change if they export `macc`.
2. **Extras we depend on** (not in TRD §8.1, but in their CLAUDE.md; please keep them): `simulate` -> `upfront_usd`, `tonnes_per_year` per upgrade (plan_table, Nessie bills use `upfront_usd`; without it finance refuses to book); `optimize` -> `status`, `p_loss`, `hist_bins`, `tonnes_needed`, and when infeasible `shortfall_tonnes`, `cheapest_extra` [{upgrade_id, cost_per_tonne, tonnes_per_year}]; `baseline(building_id)` -> `{annual_spend_usd, tonnes_per_year}`. Output shapes we check: hist_bins = [{x0,x1,count}] (30 bins).
3. **target_pct scale:** their doc marks 0-100 as "unconfirmed". Agent side sends 0-100 (Goal.target_pct, slider 0-80, default 40). Please confirm.
4. **FeasibleUpgrade class:** their doc mirrors it in `engine/models.py` until schemas land. We pass instances of `app.schemas.upgrades.FeasibleUpgrade` (on lane-support/agent). Please accept those (or `model_validate` them); ids are `"<building_id>:<type>"`.
5. **Owner-included unverified upgrades:** we send them in `simulate()` with `include_in_optimizer=True` (a copy); upgrades with the flag False are left unflagged. No separate "explicit include" parameter is used.
6. **Exclusions:** we pass excluded building ids and excluded upgrade ids together in one list to `macc` and `optimize` (matches their doc). `macc` therefore omits excluded buildings' bars.
7. **Building inputs:** their `buildings.py` reads profile.json + interior.json. `floor_area_sqft` / `envelope_area_sqft` exist only for the hero (interior.json); other buildings fall back to `rba_sqft`. Sizes come from FeasibleUpgrade anyway.
8. **Baseline from Nessie:** for `NESSIE_MODE=live` they call `nessie_client.get_bills`; our `Bill` is `{bill_id, building_id, month 'YYYY-MM', amount_usd, kwh|None}` (integrations/nessie_client.py; the Nessie teammate may change it, tell both).
9. **One upgrade per building per category:** site engineer can emit two `envelope` upgrades for a building (window_upgrade + insulation); the optimizer will pick at most one. Expected, just so it is not a surprise.
10. **State:** `macc`/`optimize` use the latest `simulate`; we call `simulate` (memoised) before every `macc`/`optimize` and serialise actions behind one lock, but the engine cache is per process: **run uvicorn with a single worker** (DEPLOY.md says so).
11. **Speed:** an owner action must finish < 3 s including `simulate`+`macc`+`optimize`+`baseline` per building; `simulate` is skipped when nothing changed, so `optimize` is the hot path (their target < 1 s for 10 buildings).
12. **Their own inconsistency:** CLAUDE.md says `PULP_CBC_CMD` no longer exists and to use `COIN_CMD`, but the latest commit message says "solve with PULP_CBC_CMD". Whichever works, the CBC binary must exist on the Vultr box (see DEPLOY.md).
13. **requirements.txt:** their branch adds `numpy==2.4.6` and `pulp[cbc]==3.3.2`; ours has other edits, expect a trivial merge conflict.
