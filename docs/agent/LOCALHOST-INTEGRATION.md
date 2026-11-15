# Localhost integration verification

Preview: http://localhost:5178. Backend: http://localhost:8118.
Worktree: /private/tmp/hawklens-portfolio-preview; detached HEAD 5708997.
No commits, pushes, branch merges, resets, or edits to other worktrees.

## Data and runtime

Backend runs with scripts/run_server.sh demo, ENGINE_MODE=live, CACHE_MODE=read_only,
NESSIE_MODE=stub, with a gitignored nonsecret backend/.env. The numerical engine is
real; banking is simulated. Frontend uses VITE_API_URL=http://127.0.0.1:8118,
VITE_EMISSIONS_3D=1, VITE_DEMO_RUN_ID=ro_investigator.

Source inventory, profiles, images, survey results, and archived plan records came
from lane-data/backend/data and cache. Preview data is a disposable copy at
/private/tmp/hawklens-full-integration-runtime/data; cache is the earlier disposable
copy /private/tmp/hawklens-portfolio-runtime/cache. Recorded image paths were
relocated only in copied image records. Original files were not rewritten.
All 1,173 original data/cache files still match the prior SHA-256 manifest.

The saved preview run remains ro_investigator, plan 91235cb8b3dd, target 40%,
risk lambda 0.2. For optimization testing, the browser used a separate actual
backend on port 8120 with browser-test-data-2. Requests were redirected to that
backend, not answered with successful mocks. That test server is now stopped.
Its approval test created simulated finance records only in disposable test data.

## Page/API connections

| Pages/features | Backend connection |
| --- | --- |
| Portfolio and real eight building cards | GET /portfolio; /health; /state/{run_id} |
| Recorded survey replay and activity | GET /events/{run_id}?replay=1; /state/{run_id} |
| New survey request | POST /run exists; new external survey unavailable in this cache-only setup |
| Targets, budgets, risk preference, upgrade selection, building inclusion | POST /compose, followed by GET /state and /events |
| Building detail, investigation history and verification evidence | Backend layout/results; /investigation_trace/{id}; /co2_equipment/{id}; /media/{image_id} |
| Matterport | Recorded tour IDs via /portfolio or backend hero; live vendor Showcase SDK |
| Inspection close-ups | /co2_equipment/{id}; original /media images and recorded bounding boxes |
| Financial, emissions, risk/uncertainty results | Backend engine plan/layout widgets; /state archived plan |
| Assumptions | GET /assumptions, including sourced upgrade rates and uncertainty inputs |
| Financing approval | POST /compose approve, current plan ID and consent; stub disclosure retained |
| Documents, investment memo, funding status | Backend memo and financing attached to matching plan via /state |

Unused legacy /properties client helpers are not called by current pages; the
active Portfolio uses /portfolio. No placeholder API success fallback was added.

## Integration corrections

- Serialize owner actions and await refreshed server state before resolving them.
- Preserve saved run ID on transient connection errors; clear only a missing run.
- Surface API/loading failures globally; roll back failed input changes and prevent
  navigation after failed backend actions. Retry reloads real saved state.
- Return saved plan and existing memo with state, without creating them on GET.
  Match document/finance fallbacks to the actual current plan ID.
- Restore overview controls after approved layouts; retain persisted exclusion state.
- Expose existing engine upgrade/uncertainty assumptions and label model estimates.
- Validate goal ranges with 422 responses instead of failing inside optimization.
- Draw survey image overlays in the same uncropped coordinate frame as the image.
- Clarify replay/cache-only survey mode, histogram scenario count, and estimated
  footprint geometry. No external data, coordinates, financial values, or image
  detail were generated to fill missing information.

The working Co2Tour, InspectionEvidence, ShowcaseModal, and co2Tags files are
byte-for-byte unchanged from the start of this integration pass.

## Verification actually performed

- Backend non-live suite: 564 passed, 2 skipped, 1 deselected (live external API test).
- Frontend: 238 passed across 9 test files. Production build passed.
- Real Chromium full flow: 18 checks, all 21 routes, no uncaught page errors or
  failed API responses. Covered survey replay; backend target/risk/budget changes;
  upgrade toggles; exclusion/reinclusion; investigation history; evidence; sourced
  assumptions; risk distribution; consent/approval with explicit stub banking;
  memo/financing persistence; and refresh persistence.
- Failure paths: intentional 503 and disconnected backend show errors, retain real
  saved inputs, and never substitute sample buildings/results.
- Real Chromium tour regression: all 8 correct tours opened; native zoom and camera
  drag worked. All 23 inspection list/tag selections navigated and opened their
  matching evidence. Fannin correctly had zero tags.
- All 23 original 2048x2048 evidence images matched cached bytes. All 26 displayed
  highlights matched recorded boxes at fit, native resolution, zoom/pan and resize.
  Returning to 3D retained iframe, sweep, camera rotation and zoom.
- Tour browser report has zero uncaught page errors. Matterport logs vendor
  xr-spatial-tracking permissions-policy errors; normal tested navigation works.
- Backend logs inspected; browser flow API responses were successful. The only
  browser-injected API failure was the deliberate outage test.

Reports and screenshots: /private/tmp/hawklens-full-integration-runtime/
(full-flow-report.json, failure-path-report.json, tour-regression-browser-report.json).
Browser scripts are uncommitted in the preview root.

## Remaining limitations

- All 23 tags are observation positions, labeled Photo taken here; zero verified
  fixture anchors. No fabricated fixture coordinates.
- Recorded annotations contain mistakes: e.g. Legacy Pointe has a diffuser label
  on a FIRE alarm and a fluorescent-light box on blank ceiling. Some Paragon
  equipment identities are uncertain. Alignment to saved boxes is verified;
  correctness of the original labels is not. No source records were corrected.
- Original blur/privacy masks remain; no AI enhancement or invented image detail.
- New external surveys require unavailable live credentials/cache entries; only
  recorded survey replay was verified locally. No live external API tests ran.
- Costs, energy/emissions savings and NPV are engine-modeled estimates from saved
  inputs and disclosed assumptions, not measured savings or contractor quotes.
- Assumptions/uncertainty parameters are inspectable; risk preference is actionable.
  There is no general editable simulation-assumptions UI.
- Banking and financing booking are stub-only; no real transaction was made and
  real balances are unavailable. Missing geometry, imagery or financial records
  remain unavailable. No replacement thumbnails or data were invented.
- Demo backend retains its existing single-user/current-plan persistence design;
  multi-user transaction isolation was not added or tested.

## Files changed in this integration pass

The preview already contained the uncommitted Portfolio/Matterport work. The list
below compares this pass with its preserved starting snapshot; prior working tour
files remain intact. backend/.env is a gitignored runtime-only addition.

- `failure-path-browser.mjs`
- `frontend/src/components/RecordedImage.jsx`
- `full-flow-browser.mjs`
- `full-tours-browser.mjs`
- `backend/app/main.py`
- `backend/app/schemas/goal.py`
- `backend/tests/test_main_routes.py`
- `frontend/src/App.jsx`
- `frontend/src/components/Truth.jsx`
- `frontend/src/components/widgets.jsx`
- `frontend/src/lib/store.jsx`
- `frontend/src/lib/store.test.jsx`
- `frontend/src/lib/viewModels.js`
- `frontend/src/lib/viewModels.test.js`
- `frontend/src/pages/Assumptions.jsx`
- `frontend/src/pages/BuildingDetails.jsx`
- `frontend/src/pages/BuildingExcluded.jsx`
- `frontend/src/pages/Documents.jsx`
- `frontend/src/pages/ExpandedPortfolioModel.jsx`
- `frontend/src/pages/ExpandedSurveyImage.jsx`
- `frontend/src/pages/InvestmentMemo.jsx`
- `frontend/src/pages/PlanPreferences.jsx`
- `frontend/src/pages/Portfolio.jsx`
- `frontend/src/pages/RiskAndTarget.jsx`
- `frontend/src/pages/StartSurvey.jsx`
- `frontend/src/pages/SurveyEvidence.jsx`
- `frontend/src/pages/SurveyInProgress.jsx`
- `docs/agent/LOCALHOST-INTEGRATION.md` (this report)
- `backend/.env` (gitignored runtime configuration)
