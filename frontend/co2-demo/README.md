# Verified CO₂ highlighting in the Matterport tour

Behind `VITE_EMISSIONS_3D=true`. Tour behaviour from the Codex 3D work (`codex-3d-work` 229f721), adapted to main's
`ShowcaseModal` (opened from a Portfolio building card or from the ⌘K search). A building whose Matterport model is **a
scan our agents surveyed**, with **verified** CO₂-emitting equipment (lighting fixtures with their type, air diffusers), gets:

- the tour through the **Showcase SDK** with one **observation marker, "Photo taken here"**, per verified item, on the sweep
  where its evidence photo was recorded. No 3D fixture position is recorded, so no marker claims to sit on a fixture;
- beside it, the **list** of every verified item (all of them: there is no CO₂ ranking, see below). Selecting an item (in the
  list, or its marker in the tour) flies to that sweep and turns to the evidence face: up to the ceiling (+80° pitch) for
  ceiling-face evidence, level for wall-face evidence;
- **Inspection Close-Up / View evidence**: the original recorded image with the recorded object outline (yellow ellipse at
  the stored box bounds, or the stored polygon), plus the claim and the verifier's result.

Every other building, the flag off, or a backend without the data: **the iframe, unchanged** — no markers, no list, nothing
invented. If the SDK cannot start (no `VITE_MATTERPORT_SDK_KEY`, or an error) the iframe is shown and the list stays,
read-only. Works in light and mission (dark) mode (`Co2Tour.css`).

"Top verified CO₂ areas": an area is a panorama where verified items were photographed; areas rank by how many verified
sources were seen there (ties in survey order), at most 3, never padded (`topAreas` in `src/lib/co2Tags.js`). Items carry
no CO₂ quantity, so the rank is a count of verified sources, not tonnes. Markers are placed only for the shown areas.

Cards and ⌘K search list only the demo portfolio's buildings (GET /portfolio, `src/lib/portfolioApi.js`); every other
stored Matterport tour is hidden. The building count follows Lane A's portfolio.json.

Files: `src/components/ShowcaseModal.jsx` (wraps the iframe), `src/components/Co2Tour.jsx` + `.css` + test,
`src/components/InspectionEvidence.jsx` + test, `src/lib/co2Api.js`, `src/lib/co2Tags.js`, `src/lib/portfolioApi.js`, `e2e/emissions.spec.js`,
`playwright.config.js`, `vitest.config.js`, `package.json` (`@matterport/sdk` 1.6.2; test tooling), this folder.

## Backend
One backend, the same `VITE_API_URL` as the rest of the site. The highlighting needs, on that backend:
- `GET /co2_equipment/{building_id}` in the Codex version (with `image_marks` and `placement`; not on `main` yet);
- the survey data behind it: `buildings/<id>/interior.json`, `claims.json` (with the recorded marks), `images.json` and the
  cached panorama lists (main's shipped data has `interior.json` for Harwin only);
- the surveyed scans in the Matterport store (`data/matterport/models/`): main ships 8 stock Houston models, none of
  which is one of our scans. `backfill_our_scans.py` adds ours using the backend's own Matterport client and store.
Until then the feature is dormant (every tour shows as before).

## Showing our 8 buildings on the Portfolio
To show our 8 buildings, fetch `GET {VITE_API_URL}/portfolio` and render one card per building, opening `showcase_url` in
`ShowcaseModal`; the CO₂ tags then match automatically by model id.
- Each building has `building_id, name, address, lat, lon, matterport_model_id, showcase_url, stories, sqft, year_built`
  (sample: `docs/agent/samples/portfolio.json` on `lane-support`); anything not recorded is `null`, never filled in.
- Use `matterport_model_id` as the property id passed to `ShowcaseModal` (it builds the tour from `property.id`, and that id
  is exactly the scan our tags belong to); `showcase_url` is the same tour as a link (`show_url` in the modal's shape).
- `showcase_url` is null when Matterport does not report the tour as viewable: show no tour for that card.
- 7 of the 8 have verified CO₂ sources (23 tags); 7900 Fannin has a tour but no interior survey, so it shows the plain tour.
- CORS: the backend allows `http://localhost:5173` and `:3000`. If Vite moves to another port (5173 busy), start the
  backend with `CORS_ORIGIN_REGEX='http://(localhost|127\.0\.0\.1):\d+'` or pin the dev port with `--port 3000`.

## Run locally
```bash
cd frontend
cp <your .env.local with VITE_MATTERPORT_SDK_KEY> .env.local     # git-ignored
VITE_API_URL=http://localhost:8000 VITE_EMISSIONS_3D=true npm run dev -- --port 3000 --strictPort
```
Add our surveyed scans to the backend's Matterport store (needs Matterport credentials; read-only against Matterport):
```bash
cd backend
(set -a; . ./.env; set +a; export MP_TOKEN_ID="$MATTERPORT_API_KEY" MP_TOKEN_SECRET="$MATTERPORT_API_TOKEN"
 python ../frontend/co2-demo/backfill_our_scans.py --api http://localhost:8000)
```

## Check
```bash
cd frontend
npm test                                   # unit tests (Vitest): placement, selection, evidence outlines, fallbacks
E2E_SITE=http://localhost:3000 E2E_API=<the site's VITE_API_URL> npm run e2e   # every Portfolio tour, light and dark
node co2-demo/check_matches.mjs            # which Portfolio buildings match, and markers each (needs the backend)
```
