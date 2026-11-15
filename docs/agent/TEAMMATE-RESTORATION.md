# Teammate feature restoration — isolated localhost preview

Frontend: http://localhost:5178 · Backend: http://localhost:8118
Worktree: /private/tmp/hawklens-portfolio-preview · detached HEAD 5708997
No commit, push, reset or branch merge. Source worktrees are unchanged.

## Preservation and source integrity

Before edits: /private/tmp/hawklens-restoration-before contains source copies,
uncommitted binary diff, status, SHA-256 manifest and a copy of prior runtime data.
Runtime data/cache now reside at /private/tmp/hawklens-restoration-runtime/{data,cache}.
Cache was cloned from the disposable prior cache, not regenerated. Only copied
images.json file paths were relocated; images, evidence coordinates and survey
records were not regenerated. All 1,173 original lane-data data/cache files match
the original SHA-256 manifest. Co2Tour.jsx, InspectionEvidence.jsx, ShowcaseModal.jsx
and co2Tags.js remain byte-identical to the pre-restoration preview.

The frontend retains RunProvider and the backend retains the final CVaR numerical
engine, investigator, verifier, neutral memo guardrails, compose lock, approval
and idempotency controls. Banking remains stub-only. No live banking write ran.
The current preview retains plan 91235cb8b3dd at the original 40% target; tests
that changed target/risk/budget or approved stub funding used flow-test-data on
port 8120. That temporary server is stopped after testing.

## Fetch and branch ledger

Ran git fetch origin successfully. origin/main advanced from ad758b1 to c8147cb.
The new commit ships an older deployment dataset; it was not copied over the
richer original eight-building investigator data. A missing commit below means
not reachable from the preview's committed HEAD; the preview deliberately has
no integration commits, so content integration is recorded separately.

| Branch/ref | Head | Commits not reachable from agent |
| --- | --- | --- |
| `agent` | `5708997` | 0 |
| `agent-final` | `214a40d` | 0 |
| `emissions-3d` | `a46356e` | 1 |
| `frontend-wiring` | `9598d6b` | 0 |
| `fw-emissions-3d` | `a46356e` | 1 |
| `lane-data` | `4fa6f2f` | 0 |
| `lane-support` | `2f898d3` | 3 |
| `main` | `dbbb3b9` | 9 |
| `matterport-ui-co2` | `c85b9a4` | 5 |
| `origin` | `c8147cb` | 16 |
| `origin/agent` | `5708997` | 0 |
| `origin/agent-final` | `214a40d` | 0 |
| `origin/emissions-3d` | `a46356e` | 1 |
| `origin/frontend-wiring` | `9598d6b` | 0 |
| `origin/lane-data` | `4fa6f2f` | 0 |
| `origin/lane-support` | `ca23b34` | 1 |
| `origin/main` | `c8147cb` | 16 |
| `origin/matterport-ui` | `fff15d6` | 3 |
| `origin/matterport-ui-co2` | `c85b9a4` | 5 |
| `origin/nessie_data` | `cb1722a` | 3 |
| `origin/quant-engine` | `ec6aedf` | 0 |
| `origin/ui-first-draft` | `10be5c2` | 0 |

Complete missing-commit lists: /private/tmp/hawklens-restoration-results/branches.json.

## Actual teammate implementations incorporated

| Source | Implementations | Current access / integration |
| --- | --- | --- |
| origin/main b97229c, Vedika | TopoBackground and ClickSteam components/styles | Animated contour background and pointer smoke; reduced-motion handling retained/added. ClickSteam existed unmounted upstream; now explicitly mounted. |
| origin/main a2cabc3, Vedika | CommandPalette, MissionControl components/styles | Search button and Cmd/Ctrl+K; page navigation; eight real buildings; correct enhanced tour opens. Persistent light/dark theme. |
| matterport-ui / matterport-ui-co2 e952354, fff15d6, c85b9a4, Samvidab / Lane B | app/matterport package: client, schema, backfill, models, parsers, queries, service, store and routes | GET /properties, /properties/{model}/thumbnail; portfolio joins by exact recorded survey model ID. Existing corrected preview tour components preserved instead of regressed to old source. |
| Existing mp-co2 demo store | Seven recorded model JSON files and original cached JPEG thumbnails | Copied only records matching seven surveyed model IDs. Seven real card images visible; Fannin has no cached thumbnail and remains unavailable. No unrelated models imported. |
| origin/main 116ce67, ad758b1, Vedika | LiveMemo, memoApi and document/PDF routes | Documents and expanded memo: generate/regenerate current draft, render guarded memo, download branded PDF. Added stale-plan/run checks under shared compose lock; no finance call. Existing funding records and Markdown access preserved. |
| origin/main ad758b1, Vedika | records.profile_from_portfolio | Snapshot fallback copied into newer records agent while retaining tour publication and source_fields. Only missing kit/files fall back; auth/API failures are not hidden. |
| origin/main / nessie_data 0867940, 1f763d7, cb1722a, Vedika | utility_research, simulation_assumptions, pricing_assumptions, building_context, energy_estimate, actual_bills | Actual source implementations imported, with configured runtime paths; prior utility implementation retained separately. New /research page exposes saved source research and calls the existing explicit-input energy and CSV validation functions. No automatic external research or guessed rates. |
| origin/main 58ecff2, Vedika | Dedicated building-account bill mapping | Optional NESSIE_BUILDING_ACCOUNT_* read support ported into existing safe adapter. Missing money/kWh fields are never invented. Tested against isolated fixture responses, not the real bank. Unsafe replacement transfer/account methods were not copied. |
| 9b9771a, Samvidab | Cross-tab goal persistence concept | Adapted to backend-owned results using storage notifications and saved-state refresh; two real browser tabs verified risk recalculation synchronization. Prototype deriveModel and local financial figures were not restored. |
| Existing frontend-wiring and support implementations | Footprint map, expanded tour, source images, curve selection | Restored visible homepage map link, unclipped target-gap link, enhanced expanded-tour link, exact source-image selection, highlighted selected upgrade text, owner-included labels, safe navigation on failed bar selection. |
| Existing saved data and read APIs | Runs, archived plans, memos and research events | New /history page exposes real saved snapshots and complete recorded event histories, including event-only research runs. Viewing history never restores/recalculates/overwrites current plans. |

The new History/Research pages and reconciliation API are integration glue for
existing saved records and teammate functions; they do not substitute a second
optimization engine or mock successful backend results.

## Verified results

- Backend non-live suite: 571 passed, 2 skipped, 1 live-marked test deselected.
- Frontend: 239 passed across 10 test files; production build passes.
- Final server-restart smoke check: correct current plan, real Paragon tour ready with three tags, and original Markdown download byte-identical to backend memo.
- Restored-feature real Chromium suite: 9 checks, no uncaught page errors, console
  errors or failed backend responses. Includes native PDF download, real memo
  generation without funding, persisted theme, real thumbnails/search, research,
  explicit-input energy calculation, history and restored map/gap navigation.
- Additional real Chromium navigation: 4 checks, no page errors: search opens the
  exact Harwin tour; expanded tour retains its five tags; selecting a source opens
  that exact image; returns to original plan.
- Cross-tab browser check: Growth/Balanced changes recalculated by actual backend
  synchronize another tab; original Balanced setting restored in disposable test data.
- Full existing flow: 18 checks, all 21 original routes, no page errors or failed API
  responses; target/risk/budget, upgrades, exclusion/reinclusion, investigation,
  evidence, assumptions, risk metrics, stub approval and persistence all passed.
- Matterport regression: all 8 correct tours ready; all 23 tag/evidence interactions
  passed; 26 recorded highlights aligned at fit/native size/zoom/pan/resize; original
  2048x2048 images byte-identical; native camera zoom/drag and return to same tour
  state passed. Fannin remains zero tags. No uncaught page errors. Vendor logs
  xr-spatial-tracking permissions-policy messages; tested navigation still works.
- Failure-path browser tests preserve real saved inputs, show backend errors, and
  never substitute sample data during intentional API outages.
- Initial findings corrected during testing: event-only runs omitted from history;
  relocated copied image paths; memo table formatting; clipped/overlapping button;
  stale unit-test fixture returned an unchanged risk layout; corrected fixture now
  models the real backend response and waits for actual state. One initial smoke
  suite invocation lacked sandbox permission for its temporary HTTP listener;
  subsequent permitted full suites passed. No failed final application tests.

Reports, logs, PDF and screenshots: /private/tmp/hawklens-restoration-results/.
Before/after: before-portfolio.png / after-portfolio.png;
before-documents.png / after-documents.png; before-risk.png / after-risk.png.
Additional images: after-mission-control.png, after-search.png,
after-search-tour.png, after-expanded-tour.png, after-selected-survey-image.png,
after-research.png and after-history.png. Browser scripts remain uncommitted.

## Remaining unavailable or intentionally excluded

- No cached thumbnail for Fannin; no invented replacement.
- No verified 3D fixture anchors: 23 Photo taken here fallbacks remain. Source
  annotation mistakes and original blur/privacy masks are not repaired by invention.
- No actual utility-bill CSV records supplied. Validator is accessible and unit
  tested with explicitly synthetic fixtures; no actual bill dataset was fabricated.
  Property-specific saved tariff research/consumption is unavailable.
- Live external research needs credentials/dependencies and a separate authorized
  cache-writing workflow; cache-only preview exposes recorded sources and does not
  claim a fresh search. Imported scripts were not run to regenerate saved results.
- Raw Houston research is shown as a cited, not independently audited artifact;
  active engine assumptions remain separate. Older pricing_assumptions outputs
  containing placeholders were not installed as numerical-engine defaults.
- General simulation-assumption editing has no completed teammate UI to import;
  current assumptions stay read-only. Existing target/budget/risk and optimization
  controls work; internal set_assumption functionality is preserved.
- Workspace was explicitly reverted by 4133682; it is not silently resurrected.
  Fixed pages retain the existing architecture instead of replacing it with an
  old frontend. Full composer widget-order/why rendering remains a separate gap.
- Full Matterport PI/vector floorplan/glTF/webhook/matching-platform tasks were
  not completed in source and are not claimed implemented. Existing recorded room
  labels and available tour functionality remain accessible.
- The wholesale origin/main Nessie adapter reintroduces a transfer shape the
  support lane demonstrated is rejected and removes reserve get-or-create behavior.
  Kept the compatible optional bill mapping and existing safer transaction logic.
- c8147cb older deployment records, prototype financial arrays and hardcoded
  building_viewer.py were not copied over verified observations or live engine output.

## Files changed in this restoration pass

Compared with the preserved starting source, not just Git HEAD:

- `backend/app/agents/building_context.py`
- `backend/app/agents/energy_estimate.py`
- `backend/app/agents/pricing_assumptions.py`
- `backend/app/agents/simulation_assumptions.py`
- `backend/app/agents/utility_research_legacy.py`
- `backend/app/documents/__init__.py`
- `backend/app/documents/routes.py`
- `backend/app/matterport/__init__.py`
- `backend/app/matterport/backfill.py`
- `backend/app/matterport/client.py`
- `backend/app/matterport/models.py`
- `backend/app/matterport/parsers.py`
- `backend/app/matterport/queries.py`
- `backend/app/matterport/routes.py`
- `backend/app/matterport/schema.py`
- `backend/app/matterport/service.py`
- `backend/app/matterport/store.py`
- `backend/app/reconciliation.py`
- `backend/tests/test_restored_features.py`
- `frontend/src/components/ClickSteam.css`
- `frontend/src/components/ClickSteam.jsx`
- `frontend/src/components/CommandPalette.css`
- `frontend/src/components/CommandPalette.jsx`
- `frontend/src/components/LiveMemo.jsx`
- `frontend/src/components/MissionControl.css`
- `frontend/src/components/MissionControl.jsx`
- `frontend/src/components/TopoBackground.css`
- `frontend/src/components/TopoBackground.jsx`
- `frontend/src/lib/markdown.test.jsx`
- `frontend/src/lib/memoApi.js`
- `frontend/src/pages/History.jsx`
- `frontend/src/pages/Research.jsx`
- `nessie/__init__.py`
- `nessie/actual_bills.py`
- `restored-features-browser.mjs`
- `restored-flow-browser.mjs`
- `restored-navigation-browser.mjs`
- `restored-tours-browser.mjs`
- `backend/app/agents/memo.py`
- `backend/app/agents/records.py`
- `backend/app/agents/utility_research.py`
- `backend/app/config.py`
- `backend/app/integrations/nessie_client.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- `docs/agent/samples/approved.json`
- `frontend/src/App.jsx`
- `frontend/src/components/Navigation.jsx`
- `frontend/src/components/Page.jsx`
- `frontend/src/lib/markdown.jsx`
- `frontend/src/lib/store.jsx`
- `frontend/src/pages/BuildingDetails.jsx`
- `frontend/src/pages/Documents.jsx`
- `frontend/src/pages/ExpandedBuildingModel.jsx`
- `frontend/src/pages/ExpandedSurveyImage.jsx`
- `frontend/src/pages/InvestmentMemo.jsx`
- `frontend/src/pages/PlanDetails.jsx`
- `frontend/src/pages/PlanPreferences.test.jsx`
- `frontend/src/pages/Portfolio.jsx`
- `frontend/src/pages/SurveyEvidence.jsx`
- `frontend/src/test/fixtures/approved.json`

Runtime-only: backend/.env now selects isolated restoration data/cache; the PDF dependency is installed only in restoration-runtime/python-extra, not in the shared virtualenv.

The final memo toolbar exposes Generate/Regenerate, PDF and original Markdown download above the long memo content. Formatting corrections preserve the memo bytes. Both final servers remain running; only the disposable test server on 8120 was stopped.
