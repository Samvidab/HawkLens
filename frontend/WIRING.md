# Wiring the pages to the backend

Branch `frontend-wiring` (off `ui-first-draft`). The Figma pages keep their layout and components and show **only data from the
backend**. Strict demo mode is always on: there is **no prototype fallback**. A page that needs a run and has none shows
"No survey data yet" with a link to start a survey (`RequireRun` in `components/Truth.jsx`); a missing value reads
**"not available"**, never a sample figure.

## Nothing shown is invented
| rule | how |
|---|---|
| No prototype fallback, ever | `App.jsx` wraps every data page in `RequireRun` (needs a layout, a run, or the portfolio). `lib/model.js` no longer has the invented plan model; the prototype's constant arrays are gone from every page. |
| No AI-generated or schematic pictures | `assets/evidence-*.png` (AI-generated) and the schematic `portfolio-3d*.svg` / `building-model*.svg` are deleted. Pictures are the survey's own images (`/media/{id}`), the real footprints (`FootprintMap`, WKT from the records) or the Matterport tour; otherwise "not available". |
| STUB badge on any stub value | `<Stub/>` (orange "STUB") next to every engine number when `plan_table.sample_pricing` or `health.engine_mode == 'stub'`, and next to bookings when `health.nessie_mode == 'stub'`. Every page footer (`<Sources/>`) names the pricing and banking source. |
| Estimates labelled | `<Estimate/>` on the building baseline (`baseline.basis = "benchmark estimate"`), assumed upgrades, estimated footprints and window counts. |
| Memo numbers only from the plan | the memo page and Documents render the backend's memo markdown verbatim (the backend number-checks it against the plan JSON); download as `.md`. |
| Unknown stays unknown | `targetModel().covered` is `null` (shown as "Coverage not available") without both tonnes figures; a sum with any missing part is not shown. |
| Accounts | the source account's name and balance are not exposed by the backend (the Nessie sandbox does not update balances): shown as "Operating account" / balance "not available". The reserve is "Hawk Lens Retrofit Reserve" (the backend's name). |
| Assumptions | `GET /assumptions` (new) serves the engine's own `assumptions.json` values with their recorded sources. |

## Run it
```bash
# backend (from the warm cache: no network, a full survey takes ~6 s)
cd backend && CACHE_MODE=read_only ENGINE_MODE=live scripts/run_server.sh        # http://localhost:8000
# frontend
cd frontend && npm ci && VITE_API_URL=http://localhost:8000 npm run dev          # http://localhost:5173
```
`VITE_API_URL` (or the older `VITE_API_BASE`) defaults to `http://localhost:8000`. The backend allows `http://localhost:5173`
and `:3000` by default; for a deployed frontend set `CORS_ORIGINS` on the server. Optional `VITE_DEMO_RUN_ID`: a recorded run
id; "Replay the recorded survey" (shown only when it is set) replays that run's feed instead of surveying.

## The pieces (`src/lib/`, `src/components/`)
| file | what |
|---|---|
| `api.js` | `startRun(goal)` POST /run, `openEvents(runId, {onEvent,onDone,onEnd,onError,replay})` SSE, `getState(runId)`, `compose(runId, type, payload)` POST /compose, `getPortfolio/getRegistry/getHealth/getAssumptions`, `mediaUrl(id)`. Errors are `ApiError(status, message)` (409 stale plan, 422 bad payload, 502 Nessie). |
| `store.jsx` | `RunProvider` + `useRun()`: `{runId, phase, events, state, layout, portfolio, health, busy, error, prefs, setPrefs, start, act, refresh, reset}`. Remembers the run id in `sessionStorage` (a reload resumes). `useOverview()` / `useBuildingFocus()` ask the backend for the view a page needs. |
| `viewModels.js` | Pure functions from `layout` to what each page renders. Widgets are found **by type**. Every selector returns `null` when its widget is absent; formatters return `NA` for missing values. |
| `components/Truth.jsx` | `Stub`, `Estimate`, `NA`, `useStub`, `Sources`, `NoData`, `RequireRun`. |
| `components/widgets.jsx` | `FootprintMap` (real footprints) and the widget renderers the pages reuse (floor plan, facades). |

## Flow
`StartSurvey` builds a Goal (target/budget/risk from `prefs`, buildings from `GET /portfolio`) -> `POST /run` -> `SurveyInProgress`
streams `GET /events/{id}` and advances by itself on `done` -> `SurveyComplete` -> Portfolio -> every control sends `POST /compose`.

## Page status (all wired; none static)
| page | shows |
|---|---|
| StartSurvey | the portfolio's buildings with their real data layers (records / aerial / interior) |
| SurveyInProgress / SurveyComplete | live feed, progress per layer, summary from `state.results` |
| Portfolio | target slider, metrics, upgrade summary, the real footprints (click = open building) |
| PlanDetails | metrics, abatement chart from the bars (click = `select_bar`), per-type table, recorded events |
| RiskAndTarget | histogram, expected value / chance of loss / worst 5 %, scenario count from the bins, target gap; link to Assumptions |
| BuildingDetails / BuildingExcluded | profile, baseline (labelled estimate), upgrades with toggles, Matterport tour or footprint |
| BuildingInsights | the `floor_plan` and `facade_compass` widgets |
| SurveyEvidence / ExpandedSurveyImage | the survey's images, verifier boxes, claims, verifier notes, which in-plan upgrades the image supports |
| PlanPreferences | budget chips scale with the plan's cost; risk chips live when `risk_supported` |
| FinancingApproval / FundingConfirmation / FundingAccount | totals and allocation from the plan, `approve`, Nessie ids; "funded" only when executed |
| InvestmentMemo / Documents | the backend memo (Markdown), the funding record once executed; nothing else is listed |
| Assumptions | `GET /assumptions` |

## Behaviour worth knowing
- **No budget cap by default** for a real run.
- The live stream ends at `done`. After a reload and after every action the store re-reads the run's recorded events.
- **Risk scale:** the engine maximises `E[NPV] + lambda x CVaR5`: Growth 0, Balanced 0.2, Cautious 0.4. The effect saturates early on the real Houston portfolio.
- Money from the API is raw USD (can be `null`): `usdK()` shows "$1,280k", "not available" for null.

## Tests
```bash
npm test            # 225 unit tests: api client, SSE, view-models, store, preferences, and the strict audit
                    # (pages/Strict.test.jsx): every route x (no run + 6 sample layouts) never shows a prototype string or
                    # image (src/test/forbidden.js); STUB and estimate labels appear where they must.
npm run e2e         # Playwright against a RUNNING backend: goal form -> live survey -> workspace -> slider -> plan -> risk ->
                    # building toggle -> evidence -> approve -> funded; reload resume; risk control; strict audit of every
                    # route without a backend and with a real run. Skips if no backend.
npx playwright install chromium   # once
```
Screenshots land in `e2e/screens/` (gitignored). Unit-test fixtures are the synthetic `docs/agent/samples/*.json`.

## Verified CO₂ sources in 3D (branch `emissions-3d`, behind `VITE_EMISSIONS_3D=1`)
On every building page the building's Matterport tour is embedded with the **Showcase SDK** (`@matterport/sdk` 1.6.2, key
`VITE_MATTERPORT_SDK_KEY` from `frontend/.env.local`, never committed) and tagged with the CO₂-emitting equipment the survey
agents saw **and the verifier confirmed**: lighting fixtures (with their type) and air diffusers / vents / grilles. No
percentages, tonnes, shares or plan links.
- Data: `GET /co2_equipment/{building_id}` (`backend/app/widgets/co2_equipment.py`): verified pins of verified
  `interior.lighting` / `interior.hvac` claims only (rejected, unverified or "unknown" -> nothing), each with the claim, the
  verifier's result and the panorama it was seen in (the scan position equal to the pin's, exact match). `tour_url` from
  `tour.json`; `tags_in_tour` only when that tour is the scan the pins came from.
- Tag: label "<equipment> seen (verified): CO₂ source"; click shows the claim, the verifier's result and a link to the
  panorama. It is anchored on the tour's own sweep for that panorama (matched by id), so no coordinate is converted or
  guessed; an item whose panorama is not in the tour gets no tag. No items -> the tour plus "No verified CO₂ sources located
  in this scan". No tour or SDK failure -> the panel only.
- Tests: `src/components/Co2Tour.test.jsx` (mocked SDK), `backend/tests/test_co2_equipment.py`, and
  `npx playwright test -c playwright.emissions.config.js` (dev server on :3000 with the flag; opens all 8 building pages;
  report in `e2e/screens/co2-tags-report.json`).
