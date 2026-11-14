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

- Sample layouts for the frontend: `docs/agent/samples/` (one JSON per situation + building_detail without Matterport + `registry.json` + README), generated by `backend/scripts/make_samples.py` from a synthetic portfolio through the real pipeline with the stub engine and Gemini off (deterministic). `tests/test_samples.py` fails if they go stale. Also fixed `storage.write_json` to accept lists of models.

- T4.3 deploy prep (nothing deployed): CORS from `CORS_ORIGINS` (+ optional `CORS_ORIGIN_REGEX`; default = local dev ports) in main.py, tested incl. preflight and the SSE stream; `app/envutil.py` (env then backend/.env) shared by llm/finance/main; `scripts/run_server.sh [demo]` (single worker, binds 127.0.0.1 by default, `demo` = CACHE_MODE=read_only); `backend/.env.example` (names only); `backend/deploy/retroalpha.service` (systemd) and `deploy/Caddyfile` (HTTPS, SSE not buffered); `backend/DEPLOY.md` (Vultr steps: setup, secrets/data via scp/rsync, run, checks, update/rollback). Needs from a human at deploy time: the Vultr instance + who deploys, the frontend domain for CORS_ORIGINS and the API domain's DNS, the repo URL.

- `scripts/smoke_test.py`: starts the app on a free port (synthetic portfolio, stub engine/Nessie, Gemini off) or tests a running server with `--url`; checks /health, /registry, /portfolio, the live SSE stream, POST /compose for every action type (goal, include_unverified, set_target/budget/risk, exclude/include building, toggle on/off, select_bar, open_building incl. back, target gap, approve with stale id -> 409, approve, repeat approve, 3 bad inputs -> 422), each layout against Layout + registry, the 3 s budget, GET /state, and live-vs-recorded events. Self-contained: 103/103 checks; against a separately started server (`run_server.sh`): 89/89. Wrapped by `tests/test_smoke_script.py`.

- Merged `lane-data` (Lane A: graph.py, store.py, interior/verifier agents, rate-limit handling, POST /run). Conflicts resolved keeping both sides. llm.py: Lane A's GEMINI_RPM pacing, 429 wait-as-told (RetryInfo) and daily-quota fail-fast (`QuotaExhausted`) + my VISION fallback (5xx/timeout only, not on quota), 60 s per-call timeout, no retry on non-transient 4xx. main.py: one copy of each route (/run from Lane A; /compose, /state, /portfolio, /registry, /events, /media, /media/mesh from this lane; Lane A's duplicate /state, /portfolio, /registry, /media, /media/mesh handlers dropped, mine are supersets: mesh `model.obj` alias + whitelist, images only served from cache/ or data/). `composer.save_state` now merges into runs/<id>/state.json (graph.py writes status/results there too). One edit to Lane A's tests/test_api.py: its fixture image moved under cache/media/ (the /media route refuses files outside cache/ and data/). 247 tests pass.
- **Integration after merging Lane A's POST /run resolution (2026-11-14): done.** `POST /run` = survey -> pricing -> compose -> one `done` (Lane A's `run_full`, which calls `replan` under the shared compose lock); `register_survey_runner(graph.survey_runner)` is registered in main.py so a `goal` action surveys missing buildings. The earlier gaps (no layout after /run; `done` before pricing/compose) are closed. `composer.save_state` and graph.py's `write_state` both merge into runs/<id>/state.json, verified by `test_compose_keeps_the_surveys_state_fields` and `test_compose_actions_never_erase_the_surveys_state_fields`; Lane A's re-merge workaround is no longer needed.

- Hero visibility (fixes STATUS-A item for Lane B): `hero_3d` is shown only when the building has a mesh (`interior_scan.json` `mesh_url`, or an extracted OBJ under cache/media/mesh/<model>/) or a `showcase_url`; `floor_plan` only with interior room data (`rooms.json`, or `interior_scan.json` `rooms`; polygons optional). Otherwise `portfolio_3d` stands in. **Contract for Lane A:** write `showcase_url` (Matterport 3D tour link) into `buildings/<id>/interior_scan.json`; when present `hero_3d` uses it instead of the mesh (`mode: "showcase"`, mesh urls null). Frontend: `hero_3d.props.mode` = mesh | showcase. New sample `docs/agent/samples/building_detail_showcase.json`; all samples regenerated.

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

## Engine contract drift for the quant teammate: first pass (docs only; superseded by the code check at the top of the next section)
Written when origin/quant-engine had only `app/engine/CLAUDE.md`. Items 1-13 below still apply unless the code check says otherwise.
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


## Quant engine code check for her (origin/quant-engine @ 742c68c, steps 1-5; checked 2026-11-14)
Method: read the code, ran her 82 engine tests (all pass), then drove `optimizer.build_problem/solve` the way our pricing node would on her 3-building fixtures (13 upgrades, 10k scenarios). Read-only: nothing in her folder was touched.

### MISSING (blocks `ENGINE_MODE=live`), most important first
1. **No contract functions yet.** `app/engine/__init__.py` exports nothing. `simulate(upgrades, assumptions)`, `macc(exclusions)`, `optimize(target_pct, risk_lambda, budget_usd, exclusions)`, `set_assumption(key, value)` and `baseline(building_id)` do not exist as the TRD §8.1 / her CLAUDE.md contract (step 6). `python -m app.integrations.engine_client` reports all five as missing. Her lower-level pieces are fine and fast (simulate 10k x 13 upgrades 0.04 s, solve 0.04 s), they just need wrapping.
2. **`risk_lambda` is ignored.** `build_problem()` and `solve()` take no `risk_lambda`; the objective is E[NPV] only (CVaR term is "step 7"). Until then the Risk slider changes nothing. (`plan_id` already accepts a `risk_lambda` argument but is called without it.)
3. **`baseline(building_id)` does not exist.** There is `buildings.baseline_kwh_per_year()` / `baseline_tonnes_per_year(BuildingFacts, assumptions)`, but nothing returns `{annual_spend_usd, tonnes_per_year}`. `annual_spend_usd` is not computed anywhere (needs kWh x `cities.<city>.electricity_rate_usd_per_kwh`, which is in assumptions.json). The building_header widget shows it. The Nessie-bills baseline is a TODO in `buildings.py`.
4. **Per-upgrade extras not exposed.** The agent side needs `upfront_usd` and `tonnes_per_year` per upgrade in `simulate()`'s output (plan_table rows, and finance refuses to book a bill without `upfront_usd`). Both exist internally (`sim.inputs[i].upfront_usd`, `sim.tonnes_per_year.mean(axis=1)`), they are just not in a contract dict yet.
5. **Wrapper has to supply the target's denominator.** `build_problem` needs `baseline_tonnes_per_year` of the portfolio; `optimize()` must compute it from the buildings in the latest simulation (`state.current()`). Please confirm: an **excluded building still counts in the denominator** (target stays "X % of the whole selected portfolio", so excluding a building makes the target harder). The agent-side stub and UI assume this.
6. **Name clash to avoid in step 6:** `app/engine/macc.py` (module) and a function `macc` in `__init__.py` share a name. After `import app.engine.macc` anywhere, `app.engine.macc` is the *module* (not callable) and our client sees no `macc` function. Bind the function last in `__init__` (`from .macc import macc as _macc` then `def macc(...)`), or export it under another module name.
7. **`simulate(upgrades, assumptions)` argument meaning:** we pass `assumptions={"discount_rate": <Goal.discount_rate>}`. Please treat it as overrides merged over assumptions.json (not a full replacement) and make `discount_rate` one of them.

### CONFIRMED PRESENT (what you asked about)
| Check | Result |
|---|---|
| `target_pct` as the CO2 constraint | **Yes.** `tonnes_needed = target_pct/100 x baseline`; constraint `sum(E[tonnes/yr] x) >= tonnes_needed`; 0-100 scale enforced (`ValueError` outside). Matches what we send. PuLP == brute force in her tests. |
| `budget_usd` | **Yes.** `sum(upfront x) <= budget_usd`, in both solvers. Probe: budget $500k, target 25 % -> `status: infeasible`, upfront $496k (<= budget), shortfall 235.7 t/yr, 3 `cheapest_extra`. |
| `risk_lambda` (CVaR) | **No**, see missing #2. (`cvar5` of the chosen plan *is* reported.) |
| `status` ok / infeasible | **Yes**, infeasible returns the max-tonnes plan (not an error). |
| `p_hit_target` | **Yes**, share of scenarios with plan tonnes >= needed. (Probe: a plan that just meets the target in expectation reports 0.57, status ok.) |
| `tonnes_needed` | **Yes.** |
| `shortfall_tonnes` | **Yes**, 0.0 when feasible; probe 80 % target -> 522.75 t/yr. Computed from expected tonnes. |
| `cheapest_extra` | **Yes**, `[]` when feasible; when infeasible up to 3 items `{upgrade_id, building_id, type, tonnes_per_year, cost_per_tonne}` (more keys than we need; fine), slot-aware (only upgrades that add tonnes). Our target_gap_card now prefers this list (falls back to our own cheapest unselected bars if the key is absent). |
| other keys we use | `plan_id` (12 hex, deterministic, same inputs -> same id), `selected`, `exp_npv`, `cvar5`, `p_loss`, `total_upfront`, `tonnes_per_year`, `hist_bins` (30 bins `{x0,x1,count}`, counts sum to ~99 % of K by design) are all returned; all plain Python floats/lists (JSON-safe). |
| `macc()` | Exists in `macc.py` (`{bars:[{upgrade_id, building_id, type, tonnes_per_year, cost_per_tonne}]}`, cheapest first, NaN-cost upgrades get no bar). Not yet exported. |

### Things to be aware of (not blockers)
- **Empty `cheapest_extra` when the target is out of reach even with everything:** the 80 % probe returned `[]` (the max-tonnes plan already uses every slot, nothing can add tonnes). Also upgrades that are merely *unverified* (not owner-excluded) are never suggested. The target-gap card then shows the shortfall with no suggestions. If you want the demo's "cheapest extra tonnes" moment to work without a budget, include unverified (`include_in_optimizer == False`, not excluded) upgrades in `cheapest_extra` (the owner can then press "include unverified"). Tell us if you add a flag for them.
- An infeasible plan is the max-tonnes plan regardless of cost (probe: exp NPV -$1.4M, p_loss 0.99). That is a sensible reading of "closest to the target"; the UI shows it as the best attempt.
- `buildings.py` is Houston-only (`baseline_kwh_per_year` raises for other cities); fine if the demo city is Houston.
- Her `FeasibleUpgrade` mirror matches ours field for field (types, categories, size units). `PROPERTY_TYPE_TO_BENCHMARK` has a TODO: real CoStar `property_type` values are in `data/buildings/*/profile.json` (lane-data) to fill it.
- Solver: `PULP_CBC_CMD` works with the pinned `pulp[cbc]==3.3.2` (her note about deprecation is right); the Vultr box needs the same pins.
