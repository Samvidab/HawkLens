# Verified CO₂ highlighting on the Matterport UI (`matterport-ui-co2`)

Behind `VITE_EMISSIONS_3D=true`. In the tour modal that `matterport-ui` already opens from a building card
(`ShowcaseModal`), a building whose Matterport model is **a scan our agents surveyed**, and which has **verified** CO₂-emitting
equipment, gets:

- the tour through the **Showcase SDK** with one tag per verified item (lighting fixtures with their type, air diffusers),
  label "<equipment> seen (verified): CO₂ source"; a click shows the claim, the verifier's result and the panorama;
- beside it, the **list** of those items: clicking one moves the tour to the panorama where it was seen and opens its tag.

Every other building (not one of our scans, or no verified items), the feature off, or our API unreachable: **their iframe,
unchanged** — no tags, no list, nothing invented. If the SDK cannot start (no key / error) their iframe is shown and the list
stays, read-only.

Nothing else changed: no other page, no design, no data source, no backend code. Changed/added files:
`src/components/ShowcaseModal.jsx` (wraps their iframe), `src/components/Co2Tour.jsx`, `src/lib/co2Api.js`,
`src/lib/co2Tags.js` (+ test), `package.json` (`@matterport/sdk` 1.6.2, a `test` script), this folder.

## Two backends, two variables
| | what | variable | here |
|---|---|---|---|
| theirs | Matterport properties (`/properties`) | `VITE_API_BASE` (their existing one) | `http://localhost:8010` |
| ours | `GET /co2_equipment/{building_id}`, `/portfolio` | `VITE_API_URL` | `http://localhost:8000` |

Our backend's CORS allows `http://localhost:5173` and `:3000` (`CORS_ORIGINS` to change it).

## Matching
By Matterport model id: their property id must equal the scan our agents surveyed (`model_id` in `/co2_equipment`). Another
scan of the same building gets nothing (tags only make sense in the scan the equipment was seen in).
Their stock backfill (`scripts.mp_backfill_slice`) takes the first Houston models from Matterport search, which are mostly
apartment units and **none of our 8 office buildings**; to see the highlighting their store must contain our scans:
`backfill_our_scans.py` stores them with **their own** client/parsers/store code.

## Commands (three terminals)
```bash
# 1) OUR backend on :8000 (agent branch, frozen demo data copied to a temp dir, cache read-only: nothing writes to the demo data)
cd /Users/mithus./Documents/Projects/HawkLens/backend
D=/Users/mithus./Documents/Projects/HawkLens/.claude/worktrees/data/backend
DEMO_TMP=$(mktemp -d /tmp/hawklens-demo.XXXXXX) && cp -R "$D/data" "$DEMO_TMP/data"
set -a; . ./.env; set +a
export DATA_DIR="$DEMO_TMP/data" CACHE_DIR="$D/cache" CACHE_MODE=read_only ENGINE_MODE=live NESSIE_MODE=stub AGENTIC_SURVEY=true
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1

# 2) THEIR backend on :8010 (their code, a store with 16 of their stock models + our 7 scans, read-only)
cd /Users/mithus./Documents/Projects/HawkLens/.claude/worktrees/mp-co2/backend
DATA_DIR=/tmp/mp-co2-demo/data CACHE_DIR=/tmp/mp-co2-demo/cache CACHE_MODE=read_only \
  /Users/mithus./Documents/Projects/HawkLens/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010

# 3) THEIR frontend with the highlighting on :3000 (your SDK key goes in frontend/.env.local, which is git-ignored)
cd /Users/mithus./Documents/Projects/HawkLens/.claude/worktrees/mp-co2/frontend
npm ci   # first time only
cp /Users/mithus./Documents/Projects/HawkLens/.claude/worktrees/support/frontend/.env.local .env.local   # first time only
VITE_API_BASE=http://localhost:8010 VITE_API_URL=http://localhost:8000 VITE_EMISSIONS_3D=true npm run dev -- --port 3000 --strictPort
```
Open <http://localhost:3000/>, click a building card.

Rebuild the store in step 2 if `/tmp/mp-co2-demo` is gone (needs Matterport credentials; read-only against Matterport):
```bash
cd /Users/mithus./Documents/Projects/HawkLens/.claude/worktrees/mp-co2/backend
P=/Users/mithus./Documents/Projects/HawkLens/backend/.venv/bin/python; N=/tmp/mp-co2-demo; mkdir -p $N/data $N/cache
(set -a; . /Users/mithus./Documents/Projects/HawkLens/backend/.env; set +a
 export MP_TOKEN_ID="$MATTERPORT_API_KEY" MP_TOKEN_SECRET="$MATTERPORT_API_TOKEN" DATA_DIR=$N/data CACHE_DIR=$N/cache CACHE_MODE=read_write
 $P -m scripts.mp_backfill_slice --limit 16                                   # their stock slice (their grid shows 24)
 $P ../frontend/co2-demo/backfill_our_scans.py --api http://localhost:8000)   # + our scans with verified items (needs terminal 1)
```
(Use `--limit 16`: their page lists the first 24 stored models sorted by id; 16 + our 7 = 23 all fit.)

## Check
```bash
cd /Users/mithus./Documents/Projects/HawkLens/.claude/worktrees/mp-co2/frontend
npm test                                  # pure logic: matching, tag placement, label/click text
node co2-demo/check_matches.mjs           # which of their buildings match ours, and tags each (needs steps 1 and 2)
```
