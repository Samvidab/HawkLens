# RetroAlpha — TRD: Agent + CoStar Data

Technical spec for the agent team, CoStar data access, and the UI composer. Read with `01-PRD.md`.

> **Rule for the coding agent:** the exact CoStar / Vexcel / Matterport function and endpoint names are **not** known in this doc. Discover them from the toolkit (Python SDK, MCP servers, or OpenAPI spec) or a starter script from the toolkit bot. Never guess a name. Wrap whatever exists behind the adapter interfaces in §4 so the rest of the code never changes.

---

## 1. Architecture

```
                    ┌──────────────── Frontend (React, other owner) ────────────────┐
                    │ goal form · widgets · 3D view · activity feed (SSE)           │
                    └───────▲──────────────────────────┬────────────────────────────┘
                            │ layout JSON / SSE events │ owner actions
                    ┌───────┴──────────────────────────▼────────────────────────────┐
                    │ FastAPI (Vultr)  /run  /events/{run_id}  /survey  /compose     │
                    └───────┬───────────────────────────────────────────────────────┘
                            │
                 ┌──────────▼──────────┐  LangGraph
                 │    Orchestrator     │──────────────────────────────┐
                 └──┬───────────────┬──┘                              │
         fan-out (Send, ≤4 at once) │                                 │
   ┌────────────────▼─────┐   ┌─────▼─────────┐   ┌──────────────┐ ┌─▼────────────┐
   │ Survey subgraph ×N   │   │ Pricing agent │   │ UI composer  │ │ Finance agent│
   │ records → aerial ∥   │   │ engine tools  │   │ registry +   │ │ Nessie tools │
   │ interior → site eng. │   └──────┬────────┘   │ templates    │ │ (approval)   │
   │ → verifier loop      │          │            └──────────────┘ └──────┬───────┘
   └──────────┬───────────┘          │                                    │
              │               quant engine (other owner)            nessie_client (other owner)
   ┌──────────▼───────────┐
   │ adapters/ costar,    │──► cache/ (disk)  ──► CoStar toolkit · Vexcel · Matterport
   │ vexcel, matterport   │
   └──────────────────────┘
   Gemini (vision + structured output) used by inspectors, verifier, composer, memo writer
   Shared state: data/ JSON files (no database)
```

**Principle: LLM decides and describes, code enforces and computes.** Gemini extracts observations from images and chooses widgets; deterministic Python applies feasibility rules, computes areas, validates schemas, and passes numbers through untouched.

## 2. Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI + uvicorn; SSE via `sse-starlette` |
| Agents | LangGraph (`StateGraph`, `Send` for fan-out, conditional edges for verifier loop); LangChain tool calling for orchestrator/pricing/finance |
| Model | Gemini via `google-genai` SDK; structured output with Pydantic response schemas; image input as bytes parts |
| Schemas | Pydantic v2 |
| Geometry | Shapely 2 + pyproj (project to UTM for areas: Houston EPSG:32615, LA EPSG:32611) |
| Images | Pillow (crop, resize, draw marks for evidence) |
| HTTP | httpx (async) |
| Concurrency | asyncio; `asyncio.Semaphore(4)` around survey fan-out and Gemini calls |
| Config | `pydantic-settings`, `.env` |
| Tests | pytest + pytest-asyncio |
| Hosting | Vultr instance (API), frontend on Vercel |

Pin versions in `requirements.txt` after install. Model names come from env, not code.

## 3. Repo layout (this role's part)

```
backend/
  app/
    main.py                 # FastAPI app, routes
    config.py               # Settings (env)
    events.py               # activity feed bus + SSE
    schemas/                # Pydantic models (§5)
      profile.py aerial.py interior.py upgrades.py claims.py
      layout.py events.py goal.py
    adapters/               # toolkit wrappers (§4) — the only code that knows CoStar APIs
      costar.py vexcel.py matterport.py cache.py geometry.py
    agents/
      graph.py              # LangGraph wiring
      orchestrator.py records.py aerial.py interior.py
      site_engineer.py verifier.py pricing.py composer.py finance.py memo.py
      llm.py                # Gemini client, retries, semaphore, JSON-schema output
      prompts/              # one .md prompt per agent
    rules/
      feasibility.yaml      # tunable thresholds (§7)
      feasibility.py
    integrations/
      engine_client.py      # calls quant engine (stub until ready)
      nessie_client.py      # owned by Nessie teammate; stub here until ready
    widgets/
      registry.py           # widget types + prop schemas (shared with frontend)
      templates.py          # default layout per situation
      resolver.py           # fills props from data_ref
    guardrails.py           # number check, step/loop caps
  data/                     # shared state (gitignored except portfolio.json)
  cache/                    # toolkit + Gemini + Nessie responses (gitignored)
  fixtures/                 # engine + nessie stub outputs
  scripts/
    explore_toolkit.py pick_portfolio.py survey_one.py replay_demo.py
  tests/
```

## 4. Adapter interfaces (fill from the toolkit)

All adapters are `async`, go through `cache.cached(key, fn)`, and return Pydantic models or raw dicts plus the saved file path for images.

```python
# adapters/costar.py
async def search_properties(city: Literal["Houston","Los Angeles"], *, property_types: list[str] | None = None,
                            min_sqft: int | None = None, limit: int = 50) -> list[dict]
async def get_property(property_id: str) -> dict          # raw record; records agent maps to BuildingProfile

# adapters/vexcel.py
async def overhead(point_wkt: str, buffer_m: float = 40) -> list[ImageRef]
async def oblique(footprint_wkt: str, orientation: Literal["N","E","S","W"]) -> list[ImageRef]
async def semantic_search(text: str, area_wkt: str, include_vectors: bool = False, k: int = 20) -> list[ImageRef]  # extra time

# adapters/matterport.py
async def models_for_property(profile: BuildingProfile) -> list[MatterportModelRef]  # match by location/address
async def panoramas(model_id: str) -> list[PanoramaRef]       # with scan positions (building + world coords)
async def rooms(model_id: str) -> RoomData                    # boundaries, types, sizes, wall graph
async def matterpak(model_id: str) -> MatterPakPaths          # local paths: obj, mtl, textures, floorplan, pointcloud
```

```python
class ImageRef(BaseModel):
    image_id: str
    source: Literal["vexcel_overhead","vexcel_oblique","matterport_pano"]
    orientation: Literal["N","E","S","W"] | None = None
    local_path: str            # cached file served at /media/{image_id}
    gsd_m: float | None = None # ground sample distance if provided
    bounds_wkt: str | None = None
    captured_at: str | None = None
```

`geometry.py`: `point_wkt(lat, lon)`, `buffer_wkt(lat, lon, meters)` (buffer in UTM, return WGS84 WKT), `footprint_polygon(profile)` (from record if present, else square from sqft/stories), `area_m2(wkt, city)`.

`cache.py`: key = sha256(adapter name + sorted params). Modes from env `CACHE_MODE=off|read_write|read_only`. In `read_only`, a miss raises `CacheMiss` (never hits network during demo). Images saved under `cache/media/`.

**First task:** `scripts/explore_toolkit.py` prints available SDK modules/methods (or MCP tools / OpenAPI paths), then pulls one record, one overhead image, one oblique, and one Matterport model list. Record the real names in `adapters/README.md`.

## 5. Schemas (Pydantic, written to `data/`)

```python
class BuildingProfile(BaseModel):          # data/buildings/<id>/profile.json
    building_id: str; costar_id: str; name: str; address: str
    city: Literal["Houston","Los Angeles"]; lat: float; lon: float
    footprint_wkt: str | None; footprint_source: Literal["costar","estimated"]
    property_type: str; building_class: str | None; year_built: int | None
    stories: int | None; rba_sqft: float | None; occupancy_pct: float | None
    matterport_model_id: str | None
    source_fields: dict[str, str]          # which CoStar fields fed each value

class Claim(BaseModel):                    # every observation an inspector makes
    claim_id: str; building_id: str; agent: Literal["aerial","interior"]
    field: str                             # e.g. "roof.existing_solar", "facade.S.glazing"
    value: str | float | bool
    confidence: float                      # inspector's own 0–1
    evidence_ids: list[str]
    marks: list[Mark] = []                 # where in the image
    status: Literal["pending","verified","sent_back","unverified","rejected"] = "pending"
    verifier_score: float | None = None; loops: int = 0; verifier_note: str | None = None

class Mark(BaseModel):
    image_id: str; label: str
    bbox: tuple[float,float,float,float] | None = None   # normalized 0–1 (x0,y0,x1,y1)
    polygon: list[tuple[float,float]] | None = None      # normalized

class AerialFindings(BaseModel):           # aerial.json
    building_id: str
    roof_type: Literal["flat","pitched","mixed","unknown"]
    roof_color: Literal["dark","light","mixed","unknown"]
    usable_roof_fraction: float            # of footprint, from Gemini, 0–1
    shading: Literal["none","partial","heavy"]
    existing_solar: bool
    usable_roof_m2: float                  # computed in code = footprint_area × fraction
    facades: dict[Literal["N","E","S","W"], FacadeFinding]
    claim_ids: list[str]; evidence_ids: list[str]

class FacadeFinding(BaseModel):
    glazing_ratio: float | None; window_count_est: int | None; notes: str | None

class InteriorFindings(BaseModel):         # interior.json (hero only for MVP)
    building_id: str; model_id: str
    lighting_type: Literal["LED","fluorescent","incandescent","mixed","unknown"]
    hvac_visible: list[str]; window_type: Literal["single","double","unknown"]
    floor_area_sqft: float | None          # from room boundaries (code)
    envelope_area_sqft: float | None       # exterior wall length × floor height × stories (code)
    claim_ids: list[str]; evidence_ids: list[str]
    pins: list[Pin]                        # findings placed at scan positions for 3D

class Pin(BaseModel):
    claim_id: str; label: str; xyz: tuple[float,float,float]; status: str

class FeasibleUpgrade(BaseModel):          # feasibility.json = list[FeasibleUpgrade]
    upgrade_id: str; building_id: str
    category: Literal["lighting","hvac","envelope","solar","roof"]
    type: Literal["rooftop_solar","cool_roof","window_upgrade","heat_pump","insulation","led_retrofit"]
    size_value: float; size_unit: Literal["kW","sqft","fixtures"]
    reason: str; confidence: float
    claim_ids: list[str]; evidence_ids: list[str]
    verified: Literal["verified","unverified","assumed"]   # led_retrofit default = "assumed"
    include_in_optimizer: bool             # False if unverified unless owner overrides

class ActivityEvent(BaseModel):            # data/runs/<run_id>/events.jsonl, streamed over SSE
    ts: str; run_id: str; seq: int
    agent: str; building_id: str | None; building_name: str | None
    kind: Literal["plan","fetch","observe","decide","verify","send_back","price","compose","act","error","done"]
    message: str                           # ≤ 90 chars, factual, no chatter
    evidence_id: str | None = None

class Goal(BaseModel):
    city: Literal["Houston","Los Angeles"]; building_ids: list[str] | None
    target_pct: float; budget_usd: float | None; risk_lambda: float = 0.5; discount_rate: float = 0.07
```

Layout schema is in `03-APP-FLOW-UIUX.md` §4 and implemented in `schemas/layout.py`.

File map in `data/`:
```
portfolio.json
buildings/<id>/profile.json aerial.json interior.json feasibility.json verification.json
plans/current.json plans/<plan_id>.json
layout.json
runs/<run_id>/events.jsonl  runs/<run_id>/state.json
memo/<plan_id>.md
```
Write files atomically (temp file + rename).

## 6. Agents

### 6.1 LLM wrapper (`agents/llm.py`)
- `async def vision_json(prompt: str, images: list[ImageRef], schema: type[BaseModel]) -> BaseModel` — Gemini with `response_schema`, temperature 0–0.2, retries ×2 with backoff, semaphore, response cached by hash(prompt + image ids + model).
- `async def text_json(prompt, schema)` same without images.
- Env: `GEMINI_API_KEY`, `GEMINI_MODEL_VISION` (strongest multimodal model on the key), `GEMINI_MODEL_FAST` (cheaper model for composer/memo). Downscale images to ≤1536 px longest side before sending.
- Log tokens per call; enforce `MAX_TOKENS_PER_SURVEY`.

### 6.2 Graph (`agents/graph.py`)

```
RunState: goal, run_id, building_ids, profiles{}, aerial{}, interior{}, claims{}, upgrades{},
          pricing{}, plan, layout, action_log[], step_counts{}

START → orchestrator_plan → fan_out ──Send("survey", {building_id})×N──► collect → pricing → compose → END
survey subgraph:  records → [aerial, interior?] (parallel) → site_engineer → verify ─┬─► done
                                                       ▲                          │ score<0.7 & loops<2
                                                       └──── reinspect(claim) ◄───┘
owner action:  START(action) → replan_router → {pricing → compose} | {compose only} | {finance → memo → compose}
```

### 6.3 Agent specs

| Agent | LLM? | Input | Does | Output | Events |
|---|---|---|---|---|---|
| Orchestrator | Gemini fast: writes plan steps | Goal, portfolio | Chooses buildings & which inspections (interior only if model id); emits plan; routes owner actions | plan steps, Send list | `plan` |
| Records | No (mapping) | CoStar record | Map fields → `BuildingProfile`; estimate footprint if absent | profile.json | `fetch` |
| Aerial | Gemini vision | 1 overhead + 4 obliques | Extract roof + facade observations as `Claim`s with marks; code computes `usable_roof_m2` | aerial.json, claims | `fetch`, `observe` |
| Interior | Gemini vision on 6–10 sampled panoramas + code on rooms | Panoramas, rooms | Lighting/HVAC/windows claims; code computes floor and envelope areas; pins at scan xyz | interior.json | `observe` |
| Site engineer | No (rules) | profile, findings | Apply `feasibility.yaml` → upgrades with sizes | feasibility.json | `decide` |
| Verifier | Gemini vision | Claim + its images + profile | Answer a yes/no-style check; score 0–1; if < 0.7 write a specific question back | verification.json | `verify`, `send_back` |
| Pricing | Tool calling (or direct calls) | upgrades, goal, action | Calls engine; never edits numbers | pricing{} | `price` |
| Composer | Gemini fast, constrained | situation summary, registry, templates | Picks template, orders/omits widgets, writes one `why` per widget; resolver fills props | layout.json | `compose` |
| Finance | Tool calling, gated | approved plan_id | Nessie: create Retrofit Reserve, transfer upfront cost, bill per contractor | confirmations | `act` |
| Memo | Gemini fast | plan JSON | Writes prose with `{{placeholders}}`; code substitutes numbers | memo.md | `done` |

**Verifier loop detail:** reinspection sends the inspector only the failing claim, its images, and the verifier's question (e.g. "Is the north half of the roof shaded by the adjacent tower?"). Max 2 loops; then `unverified`. A claim the verifier rejects outright with score < 0.3 becomes `rejected`. Upgrades depending on a non-verified claim get `include_in_optimizer=False`.

**Interior sampling:** pick panoramas spread across rooms of different types (office, corridor, mechanical) — max 10 — to bound cost.

## 7. Feasibility rules (`rules/feasibility.yaml`, tune Fri night)

```yaml
rooftop_solar:
  requires: {existing_solar: false, shading_in: [none, partial], usable_roof_m2_min: 100}
  size_kw: usable_roof_m2 * packing_factor * panel_kw_per_m2   # packing_factor 0.75, panel_kw_per_m2 0.20
  shading_derate: {none: 1.0, partial: 0.7}
cool_roof:
  requires: {roof_color: dark, roof_type_in: [flat, mixed]}   # Houston and LA both hot climates
  size_sqft: footprint_sqft
window_upgrade:
  requires_any_facade_in: [S, W]
  glazing_ratio_min: 0.35
  size_sqft: sum(facade_area * glazing_ratio for S,W)   # facade area = facade length × stories × floor_height_m(4.0)
heat_pump:
  requires_any: [{year_built_max: 1995}, {hvac_visible_contains: [boiler, rooftop_unit_old]}]
  size_sqft: floor_area_sqft or rba_sqft
insulation:
  requires: {envelope_area_sqft_known: true}
  size_sqft: envelope_area_sqft
led_retrofit:
  default: assumed
  skip_if: {lighting_type: LED}
  size_sqft: floor_area_sqft or rba_sqft
```
All constants (floor height, packing factor, panel density, year cutoff) live in YAML so the data/pitch owner can cite sources. Confidence of an upgrade = min confidence of its claims (assumed = 0.5).

## 8. Interfaces to other roles

### 8.1 Quant engine (`integrations/engine_client.py`)
In-process Python import if both live in the same FastAPI app; otherwise HTTP to the same contract. Stub returns `fixtures/engine/*.json` until the engine is ready (`ENGINE_MODE=stub|live`).

```python
simulate(upgrades: list[FeasibleUpgrade], assumptions: dict) -> {upgrade_id: {exp_npv, p_loss, cvar5, tonnes_lifetime, cost_per_tonne, hist_bins}}
macc(exclusions: list[str]) -> {bars: [{upgrade_id, building_id, type, tonnes_per_year, cost_per_tonne}]}
optimize(target_pct, risk_lambda, budget_usd, exclusions) -> {plan_id, selected: [upgrade_id], exp_npv, cvar5, p_hit_target, total_upfront, tonnes_per_year}
set_assumption(key, value) -> {ok}
```
Survey must deliver the engine: per building `rba_sqft`, `floor_area_sqft`, `envelope_area_sqft`, city, and the upgrade list.

### 8.2 Nessie (`integrations/nessie_client.py`, implemented by Nessie teammate)
```python
get_bills(building_id) -> list[Bill]
create_account(customer_id, nickname="Retrofit Reserve") -> account_id
transfer(from_account, to_account, amount, description) -> transfer_id
create_bill(account_id, merchant_id, amount, description) -> bill_id
```
Finance agent: only runs on action `approve` with a `plan_id` equal to `plans/current.json.plan_id`. One bill per selected upgrade grouped by contractor type. Emits one `act` event per call with the returned ID.

### 8.3 Frontend
- Widget registry and prop schemas: `widgets/registry.py`, mirrored as TypeScript by the frontend owner (export a JSON Schema at `GET /registry`).
- Evidence images served at `GET /media/{image_id}`; marks are normalized coordinates the frontend draws.
- Hero mesh served at `GET /media/mesh/{model_id}/model.obj` (+ mtl, textures).

## 9. API (owned by this role)

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/run` | `Goal` | `{run_id}`; starts survey + pricing + compose in background |
| GET | `/events/{run_id}` | — | SSE stream of `ActivityEvent`; `?replay=1` streams cached events with delays |
| POST | `/survey` | `{building_ids}` | feasible upgrades with reasons and evidence |
| POST | `/compose` | `OwnerAction` | layout JSON with resolved props |
| GET | `/state/{run_id}` | — | current RunState snapshot (debug + frontend reload) |
| GET | `/registry` | — | widget JSON Schemas |
| GET | `/media/{id}` | — | cached image / mesh |
| GET | `/portfolio` | — | portfolio.json |

```python
class OwnerAction(BaseModel):
    run_id: str
    type: Literal["goal","exclude_building","include_building","toggle_upgrade","select_bar",
                  "set_target","set_budget","set_risk","include_unverified","approve","open_building"]
    payload: dict
```
Replan routing:

| Action | Re-runs |
|---|---|
| exclude/include building, toggle upgrade, include_unverified, set_target/budget/risk | optimize (and macc if exclusions change) → compose |
| select_bar, open_building | compose only |
| approve | finance → memo → compose |
| goal | full run |

## 10. Guardrails

- Every agent output validated by Pydantic; on failure retry once with the validation error in the prompt, then fall back (template layout / `unknown` values).
- Composer can only use registered widget types; props never come from the LLM — they come from the resolver reading tool JSON.
- `guardrails.check_numbers(text, sources)`: every number in memo/`why` text must appear in source JSON (after rounding rules); otherwise regenerate without numbers.
- Caps: 2 verifier loops per claim; ≤ 8 tool steps per agent; ≤ 4 concurrent buildings; token budget per survey.
- Finance writes only after approval; idempotency key = plan_id (never double-book).
- No CoStar data sent anywhere except Gemini; nothing persisted outside `data/` and `cache/`.

## 11. Performance targets

| Path | Target |
|---|---|
| Owner action → new layout (survey cached) | < 3 s |
| One building live survey | < 60 s |
| Full portfolio survey live | < 2 min (else demo from cache, run one building live) |
| Replay of cached run | ~30–40 s paced for the demo |

## 12. Testing

- Unit: geometry (area of a known polygon in UTM), feasibility rules on hand-built findings, guardrail number check, layout validation.
- Golden: `survey_one.py <building_id>` against cache produces identical JSON twice.
- Contract: engine stub and Nessie stub match signatures in §8.
- Offline: `CACHE_MODE=read_only` full run with network disabled passes.

## 13. Extra time (only if MVP done by Sat 8pm)

1. Port graph to LangChain `deepagents` (orchestrator as deep agent; survey roles as subagents). Check the current deepagents API in its docs before porting.
2. Vexcel semantic image search to find candidates ("flat roof, no panels") — adds an `observe` step to the orchestrator.
3. Pins for all findings + room-type coloring data for the 3D view.
4. Ask bar: typed request → orchestrator → widgets only (confirm with CoStar it isn't a "chatbot").
5. Climate vs CFO advocate agents calling `optimize` with different λ; owner preference memory.
