# Verified CO₂ highlighting in the Matterport tour

Behind `VITE_EMISSIONS_3D=true`. In the tour modal (`ShowcaseModal`, opened from a Portfolio building card or from the
⌘K search), a building whose Matterport model is **a scan our agents surveyed**, and which has **verified** CO₂-emitting
equipment, gets:

- the tour through the **Showcase SDK** with one tag per verified item (lighting fixtures with their type, air diffusers),
  label "<equipment> seen (verified): CO₂ source"; a click shows the claim, the verifier's result and the panorama;
- beside it, the **list** of those items: clicking one moves the tour to the panorama where it was seen and opens its tag.

Every other building, the flag off, or a backend without the data: **the iframe, unchanged** — no tags, no list, nothing
invented. If the SDK cannot start (no `VITE_MATTERPORT_SDK_KEY` in `frontend/.env.local`, or an error) the iframe is shown
and the list stays, read-only. Works in both themes (`Co2Tour.css` has the mission-mode colours).

Files: `src/components/ShowcaseModal.jsx` (wraps the iframe), `src/components/Co2Tour.jsx` + `.css`, `src/lib/co2Api.js`,
`src/lib/co2Tags.js` (+ test: `npm test`), `package.json` (`@matterport/sdk` 1.6.2), this folder.

## Backend
One backend, the same `VITE_API_URL` as the rest of the site. The highlighting needs, on that backend:
- `GET /co2_equipment/{building_id}` and the `/portfolio` card fields (on `lane-support` / `agent`, not yet on `main`);
- the survey data behind it: `buildings/<id>/interior.json`, `claims.json`, `tour.json` (main's shipped data has
  `interior.json` for Harwin only and no `tour.json`);
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
npm test                                   # pure logic: matching, tag placement, label/click text
node co2-demo/check_matches.mjs            # which Portfolio buildings match, and tags each (needs the backend)
```
