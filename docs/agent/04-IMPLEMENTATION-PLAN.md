# RetroAlpha — Implementation Plan: Agent + CoStar Data

Ordered, time-boxed tasks for the coding agent. Work top to bottom. Each task has files, steps, and a check that must pass before moving on. Specs: `01-PRD.md`, `02-TRD.md`, `03-APP-FLOW-UIUX.md`.

**Clock:** starts Fri 11:45pm. Team checkpoints: **Sat 4am** one building surveyed · **Sat 10am** end-to-end demo · **Sat 4pm** composer + live re-plan · **Sat 8pm** MVP done · **Sun 2am** feature freeze · **Sun 7am** submit.

## Time budget (MVP ≈ 17–18 h of work)

| Phase | Work time | Target finish |
|---|---|---|
| 0 Setup + toolkit discovery | ~1.5 h | Sat 1:15am |
| 1 One building end to end | ~2.5 h | Sat 3:45am (AC-1) |
| — Human sleeps Sat 6–10am; agent warms cache with a full portfolio run (T2.1) | — | — |
| 2 Parallel survey, verifier, interior, first layout | ~5 h | Sat ~12:45pm (AC-2, AC-3) |
| 3 Re-plan, composer, finance, memo | ~5 h | Sat ~5:45pm (AC-4, AC-5) |
| 4 Hardening, offline, deploy | ~3 h | Sat ~8:45pm (MVP) |
| 5 Extra time | only if Phase 4 ends before 9pm | Sun 2am freeze |

This runs ~45–60 min behind the team's Sat 8pm target. If any phase overruns by > 30 min, drop the interior inspector (saves ~1.5 h; CoStar + Vexcel still meet the 2-layer rule) and use the "If behind schedule" table.

## Inputs the human must provide, and when

| Needed by | Task | Input |
|---|---|---|
| Now | T0.1 | Repo URL + folder layout; CoStar SDK install command, package name, auth key + env var name |
| Now | T0.3 | CoStar "APIs & SDKs" page/link, MCP server config, OpenAPI spec URL, toolkit-bot starter scripts, rate limits |
| Now | T1.3 | Gemini key confirmed working; model names available on it |
| Sat 1am | T1.1 | Demo city (Houston or LA) decided by the team |
| Sat 1am | T0.3 review | Human confirms real API names written in `adapters/README.md` (per-layer fields, Vexcel response format, Matterport lookup, cross-layer ID) |
| Sat ~noon | T3.3 | Quant engine: same repo (import) or separate service (HTTP) |
| Sat ~2pm | T3.4 | Nessie teammate's `nessie_client.py` with TRD §8.2 signatures |
| Sat ~6pm | T4.3 | Vultr instance up; who deploys |

If an input is missing when its task starts, stop and ask; work on the next unblocked task meanwhile.

## Git workflow

- Work on branch `agent`. Commit after every passing check (`git commit -m "<task id>: …"`) and push to remote after each commit (roughly every 30–60 min).
- Run `pytest` before every merge. Merge `agent` → `main` only at these points:

| Time | Merge | Why |
|---|---|---|
| ~Sat 12:30am | T0.1–T0.2 skeleton + T1.2 schemas + `widgets/registry.py` | Teammates build against the contracts early (pull T1.2 forward for this merge) |
| ~Sat 4am | AC-1 one-building survey | Checkpoint restore point |
| ~Sat 10am–1pm | AC-3 first layout end to end | Frontend integrates real layout JSON |
| ~Sat 4–6pm | AC-4, AC-5 re-plan, composer, finance | Live engine + Nessie wiring |
| ~Sat 8–9pm | MVP; tag `mvp` | Guaranteed fallback version |
| Sun 2am | Freeze; tag `demo` | Only bug fixes after this |

- Never merge in the last hour before judging. Never commit `.env`, `cache/`, or `data/` (except `data/portfolio.json`).

**Working rules**
- Stop and ask the human when a CoStar/Vexcel/Matterport name or field is unknown. Do not guess.
- Every toolkit, Gemini, and Nessie call goes through the cache.
- Stubs first, real integrations swapped in by env flag (`ENGINE_MODE`, `NESSIE_MODE`).
- No LLM-generated numbers anywhere in outputs.

---

## Phase 0 — Setup and toolkit discovery (Fri 11:45pm → Sat 1:15am, ~1.5 h)

### T0.1 Backend skeleton
- Create layout from TRD §3. `requirements.txt`: fastapi, uvicorn, sse-starlette, pydantic, pydantic-settings, httpx, langgraph, langchain-core, google-genai, shapely, pyproj, pillow, pyyaml, pytest, pytest-asyncio.
- `config.py` with env: `GEMINI_API_KEY, GEMINI_MODEL_VISION, GEMINI_MODEL_FAST, COSTAR_*` (names from toolkit), `CACHE_MODE, ENGINE_MODE, NESSIE_MODE, DEMO_CITY, MAX_CONCURRENT_BUILDINGS=4`.
- `GET /health`.
- **Check:** `uvicorn app.main:app` serves `/health`; `pytest` runs (0 tests OK).

### T0.2 Cache + geometry
- `adapters/cache.py` (modes off/read_write/read_only; images to `cache/media/`).
- `adapters/geometry.py` (point, buffer, footprint, UTM area).
- **Check:** tests — 100 m × 100 m square in Houston UTM ≈ 10,000 m² (±1%); read_only miss raises `CacheMiss`.

### T0.3 Toolkit discovery
- `scripts/explore_toolkit.py`: list SDK modules/methods (or MCP tools / OpenAPI paths). Pull 1 CoStar record, 1 overhead image, 1 oblique (each orientation), Matterport model list near that building.
- Write real names, params, and sample fields to `adapters/README.md`.
- **Tip:** if the toolkit provides MCP servers, connect them to Claude Code to explore data interactively; ask the toolkit bot for a starter script per layer.
- **Check:** the four sample pulls saved in cache; README lists the real call names. → **Ask human to confirm before continuing.**

### T0.4 Adapters
- Implement `costar.py`, `vexcel.py`, `matterport.py` against the interfaces in TRD §4 using the discovered names.
- **Check:** `pytest tests/test_adapters.py` (marked `live`) pulls one building through each adapter; second run is a cache hit.

## Phase 1 — One building end to end (Sat 1:15am → 3:45am, ~2.5 h) ✅ checkpoint AC-1

### T1.1 Portfolio pick
- `scripts/pick_portfolio.py`: search the demo city for office/commercial buildings; keep ones with overhead + oblique coverage; find ≥1 with a Matterport model (hero). Output `data/portfolio.json` (6–10 ids, hero flagged).
- **Check:** portfolio.json has 6–10 buildings, one `hero: true` with `matterport_model_id`. Human approves list.

### T1.2 Schemas
- All Pydantic models from TRD §5 + `schemas/layout.py` from App Flow §4.
- **Check:** round-trip tests (model → json → model).

### T1.3 LLM wrapper
- `agents/llm.py`: `vision_json`, `text_json`, structured output with Pydantic schema, retries, semaphore, response cache, image downscale.
- **Check:** a test image + toy schema returns a valid object; second call is cached.

### T1.4 Events bus
- `events.py`: `emit(run_id, agent, kind, message, building_id=None, evidence_id=None)` → append to `runs/<run_id>/events.jsonl` + in-memory queue; `GET /events/{run_id}` SSE (+ `?replay=1` paced from file).
- **Check:** curl the SSE endpoint and see emitted test events.

### T1.5 Records agent
- Map CoStar record → `BuildingProfile`; `source_fields` filled; footprint estimated if absent.
- **Check:** `profile.json` for one building with no null in required fields except allowed ones.

### T1.6 Aerial inspector
- Prompt `prompts/aerial.md`: given overhead + 4 obliques, return roof type/color, usable fraction, shading, existing solar, facade glazing/window estimates, each as a claim with normalized marks. Tell the model to output `unknown` rather than guess.
- Code computes `usable_roof_m2 = area_m2(footprint) × usable_roof_fraction`.
- **Check:** `aerial.json` + claims for one building; evidence images exist under `/media`; marks drawn on a debug PNG look right to a human.

### T1.7 Site engineer
- `rules/feasibility.yaml` + `feasibility.py` exactly per TRD §7.
- **Check:** unit tests for each rule with hand-built findings; one real building yields ≥1 upgrade with size and evidence.

### T1.8 `scripts/survey_one.py <id>`
- Runs records → aerial → site engineer sequentially, emits events.
- **Check (AC-1):** command prints feasible upgrades JSON; second run fully cached and identical. **Tell the team.**

## Phase 2 — Parallel survey, verifier, interior (Sat 3:45am → ~12:45pm incl. 6–10am sleep, ~5 h work) ✅ AC-2, AC-3

Before the human sleeps at 6am: finish T2.1, then start a full `POST /run` on the portfolio with `CACHE_MODE=read_write` so the cache warms overnight.

### T2.1 LangGraph wiring
- `agents/graph.py`: RunState; orchestrator_plan → `Send` fan-out (≤ `MAX_CONCURRENT_BUILDINGS`) → collect. Survey subgraph: records → aerial ∥ interior(if hero) → site_engineer → verify loop.
- Orchestrator: Gemini fast writes 2–4 plan steps as events; control flow stays deterministic.
- **Check:** `POST /run` surveys the whole portfolio; events stream; all `feasibility.json` files written.

### T2.2 Verifier loop
- `prompts/verifier.md`: given a claim, its images, and profile → `{score, note, question_back}`.
- Conditional edge: score < 0.7 and loops < 2 → reinspect (inspector receives only that claim + question). Then unverified / rejected per TRD §6.3. Update `include_in_optimizer`.
- **Check:** at least one `send_back` event occurs on the portfolio (if none naturally, lower threshold in a test to prove the path); `verification.json` written.

### T2.3 Interior inspector (hero)
- Sample ≤ 10 panoramas across room types; Gemini → lighting/HVAC/window claims.
- Code: floor area from room polygons; envelope area from exterior walls in wall graph × floor height × stories; pins from scan positions.
- Download MatterPak; serve OBJ/MTL/textures at `/media/mesh/{model_id}/…`.
- **Check:** `interior.json` has areas + ≥3 pins; mesh URL loads in a browser (frontend owner confirms).

### T2.4 Engine + Nessie stubs
- `integrations/engine_client.py` stub returning fixtures shaped like TRD §8.1 for the real upgrade IDs (generate plausible fixture values with a script, clearly flagged as stub).
- `integrations/nessie_client.py` stub per TRD §8.2 (coordinate: Nessie teammate replaces it).
- **Check:** contract tests pass.

### T2.5 Pricing node + first layout
- Pricing: calls `simulate`, `macc`, `optimize` with Goal; stores in `plans/current.json`.
- Composer v0: always returns the `portfolio_overview` template; resolver fills props from data.
- `POST /compose`, `GET /state/{run_id}`, `GET /registry`, `GET /portfolio`.
- **Check (AC-3):** goal in → layout JSON out; frontend renders it. **Tell the team: end-to-end works.**

## Phase 3 — Composer, re-plan, finance, memo (Sat ~12:45pm → ~5:45pm, ~5 h) ✅ AC-4, AC-5

### T3.1 Replan router
- Map `OwnerAction.type` → nodes per TRD §9 table; emit 1–3 events per action.
- **Check:** each action type changes `plans/current.json` or layout as expected; < 3 s with cached survey and stub engine.

### T3.2 Composer v1
- Situation detection (App Flow §6) in code; Gemini fast picks drops/reorders/additions within limits and writes `why` lines; validate; fallback to template.
- **Check:** scripted scenarios produce the right situation: target unreachable → `target_gap`; open hero → `building_detail` with hero_3d; rejected claim → `verification_issue`.

### T3.3 Swap in live engine
- `ENGINE_MODE=live` once the quant owner is ready; fix any contract drift on their side or in the client.
- **Check:** layouts show live numbers; stub badge gone.

### T3.4 Finance agent
- Gated on `approve` with matching `plan_id`; idempotent by plan_id; create Retrofit Reserve, transfer upfront, one bill per contractor; emit `act` events with IDs.
- **Check (AC-5):** approve in UI → Nessie IDs appear in financing_card (live mode once teammate's client is ready).

### T3.5 Memo writer
- Gemini writes prose with `{{placeholders}}` only; code substitutes from plan JSON.
- **Check:** `guardrails.check_numbers` passes on 3 different plans.

## Phase 4 — Hardening (Sat ~5:45pm → ~8:45pm, ~3 h) ✅ AC-6, AC-7, MVP

### T4.1 Guardrails
- Number check on memo and every `why`; step/loop/token caps; Pydantic retry-once on failure.
- **Check (AC-6):** test feeds a fake LLM response with an invented number → it is rejected and regenerated.

### T4.2 Offline demo
- Warm cache with a full run; `CACHE_MODE=read_only`; `scripts/replay_demo.py` paces events (~30–40 s total).
- **Check (AC-7):** full demo path (App Flow §9) with wifi off.

### T4.3 Deploy
- Run API on Vultr (systemd or `uvicorn` in tmux), CORS for the frontend domain, keys in env only. Copy `cache/` and `data/` to the server.
- **Check:** frontend on the GoDaddy domain talks to the Vultr API.

### T4.4 Rehearsal support
- Script the exact building and slider values for the 2-minute demo; make sure a `send_back` appears in the replayed feed.
- **Check:** two clean rehearsals with the team. **Sat ~9pm go/no-go on extra time.**

## Phase 5 — Extra time (Sat ~9pm → Sun 2am, only if Phase 4 done before 9pm)

Do in this order; stop at any point and keep the build green.
1. **deepagents port** — re-express orchestrator + survey roles as a deep agent with subagents (read current deepagents docs first). Enter LangChain prize only if this ships.
2. **Semantic image search** — orchestrator step that finds extra candidates via Vexcel embeddings.
3. **More pins + room coloring** for hero_3d.
4. **Ask bar** (confirm with CoStar first) — typed request → widgets only.
5. **Advocate agents** — climate vs CFO plans via different λ.

## Phase 6 — Freeze and submit (Sun 2am → 7am)

- Bug fixes only. No new features after 2am.
- Help with Devpost "How we built it": agents, Gemini (MLH), Vultr (MLH), three CoStar layers, verifier loop.
- Q&A prep for agent questions: how claims are verified, what happens when imagery is wrong, why the LLM never produces numbers, rate-limit and cost caps.

## If behind schedule

| Time | If not done | Do this |
|---|---|---|
| Sat 4am | AC-1 | Skip obliques; overhead only. Ask CoStar engineers on Discord |
| Sat 1pm | AC-3 | Composer = static template; skip interior; stub engine |
| Sat 6pm | AC-4 | Precompute layouts for scripted actions; replay them |
| Sat 9pm | Matterport | Drop interior; ship CoStar + Vexcel (2 layers) |
| Any time | Gemini rate limits | Cheaper model for inspectors, 2 concurrent buildings, demo from cache |
