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
