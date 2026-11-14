# Wiring the pages to the backend

Branch `frontend-wiring` (off `ui-first-draft`). The Figma pages keep their layout and components; each page now reads real
data when a run exists and **falls back to its prototype data when it does not** (no provider, no backend, no run yet).

## Run it
```bash
# backend (from the warm cache: no network, a full survey takes ~6 s)
cd backend && CACHE_MODE=read_only ENGINE_MODE=live scripts/run_server.sh        # http://localhost:8000
# frontend
cd frontend && npm ci && VITE_API_URL=http://localhost:8000 npm run dev          # http://localhost:5173
```
`VITE_API_URL` (or the older `VITE_API_BASE`) defaults to `http://localhost:8000`. The backend allows `http://localhost:5173`
and `:3000` by default; for a deployed frontend set `CORS_ORIGINS` on the server. Optional `VITE_DEMO_RUN_ID`: a recorded run
id; "Use cached demo survey" then replays that run's feed offline (paced ~35 s) instead of surveying.

## The pieces (`src/lib/`)
| file | what |
|---|---|
| `api.js` | `startRun(goal)` POST /run, `openEvents(runId, {onEvent,onDone,onError,replay})` SSE (closes itself on `done`), `getState(runId)`, `compose(runId, type, payload)` POST /compose (an OwnerAction), `getPortfolio/getRegistry/getHealth`, `mediaUrl(id)`. Also keeps the `matterport-ui` exports (`fetchProperties`, `fetchProperty`, `assetUrl`, `showcaseSrc`), so merging that branch is trivial. Errors are `ApiError(status, message)` (409 stale plan, 422 bad payload, 502 Nessie). |
| `store.jsx` | `RunProvider` + `useRun()`: `{runId, phase (idle/surveying/ready/error), events, state, layout, portfolio, health, busy, error, prefs, setPrefs, start, act, refresh, reset}`. Remembers the run id in `sessionStorage` (a reload resumes). `useOverview()` / `useBuildingFocus()`: **the layout depends on the view** (a focused building has no `plan_table`), so plan pages ask for the portfolio view and building pages for a focused building. |
| `viewModels.js` | Pure functions from `layout` to what each page renders (see below). Widgets are found **by type**: the composer may reorder, drop or add widgets. Every selector returns `null` when its widget is absent. |

## Flow
`StartSurvey` builds a Goal (target/budget/risk from `prefs`, buildings from `GET /portfolio`) -> `POST /run` -> `SurveyInProgress`
streams `GET /events/{id}` and advances by itself on `done` -> `GET /state/{id}` holds the `layout` -> every control sends
`POST /compose`: target slider `set_target` (when it settles, 400 ms), plan preferences `set_budget`/`set_risk`, building toggles
`toggle_upgrade`/`include_unverified`, exclude/include `exclude_building`/`include_building`, curve bar `select_bar`, open building
`open_building`, approve `approve {plan_id}`.

## Page status
| page | status |
|---|---|
| StartSurvey | **wired**: real building list and settings, starts the run |
| SurveyInProgress / SurveyComplete | **wired**: live feed, progress per layer, summary from `state.results` |
| Portfolio | **wired**: target slider (0-80), metrics, status, upgrade summary, building name; the isometric 3D picture is still the static SVG |
| PlanDetails | **wired**: metrics, abatement chart drawn from the bars (click a bar = `select_bar`), per-type table, latest events |
| RiskAndTarget | **wired**: 30-bin histogram, expected value / chance of loss / worst 5 %, target-gap card with the cheapest extra cut |
| BuildingDetails / BuildingExcluded | **wired**: real profile + baseline, real upgrades with CO2/cost/NPV, include toggles, exclude / include again; the 3D picture is static |
| SurveyEvidence | **wired**: real Vexcel/Matterport images from `/media/{id}`, the verifier's boxes drawn on the image, the claims as findings |
| PlanPreferences | **wired**: budget chips scale with the plan's cost, risk chips send `risk_lambda` (the engine does not apply it yet: `risk_supported` is false) |
| FinancingApproval / FundingConfirmation | **wired**: totals, contractor allocation, `approve` with the current `plan_id`, errors as toasts, confirmation shows the Nessie ids (says "Simulated (stub Nessie)" when the backend is in stub mode) |
| InvestmentMemo | partly: the three metrics are live; the memo prose is still the static text (`memo` widget has the markdown) |
| Documents, Assumptions, BuildingInsights, DemoDocumentNotice, FundingAccount, Expanded* | **not wired** (static); no backend data for Documents/Assumptions yet |
| `hero_3d`, `floor_plan`, `facade_compass`, `target_gap_card` as widgets | not rendered as widgets: the Figma screens have no place for 3D tours or facades; `hero_3d.props.mode` is `mesh` or `showcase` (embed `showcase_url`) |

## Behaviour worth knowing
- **No budget cap by default** for a real run (the prototype's $1500k would not fit a real portfolio; the plan costs millions).
- The activity feed ends at `done`; later actions (slider, toggles) do not add live events, so the "latest events" box on the Plan page shows the survey's last events.
- The survey screen needs a **backend with data**; with `CACHE_MODE=read_only` and a warm cache it replays the real survey in seconds.
- Money from the API is raw USD (can be `null`): `usdK()` shows "$1,280k", `—` for null.

## Tests
```bash
npm test            # 46 unit tests: api client, SSE handling, every view-model, the store (fake API, jsdom)
npm run e2e         # Playwright (Chromium) against a RUNNING backend: goal form -> live survey -> workspace -> slider -> plan ->
                    # risk -> building toggle -> evidence -> approve -> funded; reload resume; static fallback. Skips if no backend.
npx playwright install chromium   # once
```
Screenshots of every step land in `e2e/screens/` (gitignored). Unit-test fixtures are the synthetic `docs/agent/samples/*.json`
of the backend repo (no real building data is committed).
