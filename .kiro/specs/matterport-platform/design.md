# Matterport 3D Property Data Platform — Design

Implements `requirements.md`. Lives inside the existing RetroAlpha backend and reuses
its cache, config, and geometry layers. Read alongside `docs/agent/02-TRD.md`.

## 1. Architecture

```
                         FastAPI (app/main.py)
                               │
        ┌──────────────────────┼───────────────────────────┐
        │ matterport routes    │  (Phase 2: /properties ...)│
        └──────────┬───────────┴────────────────────────────┘
                   │
        ┌──────────▼───────────────────────────────────────┐
        │ app/matterport/                                    │
        │   client.py     typed GraphQL client (auth,        │
        │                 retry/backoff, 429, pagination)    │
        │   schema.py     introspection runner + report      │
        │   queries.py    GraphQL docs (built AFTER R1)       │
        │   models.py     Pydantic models (built AFTER R1)    │
        │   parsers.py    raw JSON -> models; PI parsing      │
        │   geometry.py   floorplan/Z-up conversions          │
        │   backfill.py   model index ingestion (R3)          │
        │   pi.py         Property Intelligence ingestion (R4)│
        │   assets.py     asset downloader (R5)               │
        │   matching.py   model <-> property linking (R7)     │
        │   storage.py    storage interface (local; S3 later) │
        │   sync.py       webhook + reconcile (R6, flagged)   │
        │   service.py    read API over data/ (Phase 2)       │
        └──────────┬────────────────────────┬────────────────┘
                   │ every network call      │ reads/writes
          app/adapters/cache.py       backend/data/matterport/
                   │                   backend/cache/media/
          api.matterport.com/api/models/graph
```

**Principle:** the client and cache are the only code that talk to Matterport.
Ingestion jobs are pure functions over cached responses, so they are deterministic
and rerunnable offline.

## 2. Config additions (`app/config.py`)

Add to `Settings` (env-driven, no defaults for secrets):

```python
mp_token_id: str | None = None          # MP_TOKEN_ID
mp_token_secret: str | None = None       # MP_TOKEN_SECRET
mp_api_url: str = "https://api.matterport.com/api/models/graph"
mp_max_retries: int = 5
mp_backoff_base_s: float = 0.5
mp_asset_types: str = "mesh,images"      # comma list; add "pointcloud" to include
mp_enable_webhooks: bool = False         # R6 feature flag
mp_enable_gltf_viewer: bool = False      # R9 optional viewer flag
```

`matterport_api_key` stays for backward compatibility but is unused by this platform.
Basic-auth header built in the client; the secret is never logged (redact in repr).

## 3. Data layout (`backend/data/matterport/`)

```
schema.json                      # raw introspection result (R1)
schema-report.md                 # human-readable capability report (R1)
models/<model_id>.json           # core fields + raw JSON (R3)
pi/<model_id>.json               # floors/rooms/dimensions/floorplan (R4)
assets/<model_id>.json           # asset manifest w/ checksums (R5)
properties.json                  # internal property index (R7)
links.json                       # model_id -> property_id links + method/confidence
overrides.json                   # manual override table (R7)
```

Binary assets: `backend/cache/media/mp/<model_id>/<asset>` with a `.sha256` sidecar.
All JSON writes are atomic (reuse the temp-file+rename pattern already in cache.py).

## 4. Client design (`client.py`)

- `MatterportClient(settings)` holds an `httpx.AsyncClient` with basic auth.
- `async graphql(query: str, variables: dict, *, op_name: str) -> dict`
  - routes through `cache.cached(namespace="matterport", params={op_name, variables}, fn=...)`
  - raises on transport errors, non-2xx (after retries), and GraphQL `errors[]`.
- Retry policy: retry on 429/5xx/network; exponential backoff
  `base * 2**attempt` + jitter; honor `Retry-After`; cap at `mp_max_retries`.
  Retries happen INSIDE `fn` so only the final success is cached.
- `async def paginate(query, variables, *, page_path, op_name) -> AsyncIterator[list]`
  reads `totalResults`/`nextOffset` from the response and advances `offset` until done.
- Secret redaction: `__repr__` and any logging show `MP_TOKEN_SECRET=***`.

Exact query strings and the `Model` field list are written **after** R1 introspection,
so we never guess the schema. `queries.py` / `models.py` are stubs until then.

## 5. Introspection (`schema.py`)

- Standard GraphQL introspection query → `data/matterport/schema.json`.
- Report generator walks the introspection result and prints/writes:
  - query root fields and the model-search field (name + args + pagination fields),
  - the `Model` object type's fields and nested types,
  - presence/absence of PI types (match by name heuristics: `dimension*`, `floor*`,
    `room*`, `floorplan*`, `vector*`) → sets `pi_available`.
- Output is both stdout (summary) and `schema-report.md`. No secret printed.

## 6. Coordinate handling (`geometry.py`)

- **Z-up (mesh/point cloud):** raw vertices are Z-up. For any 2D/area work we convert
  to Y-up or XY-plane explicitly; conversion functions are small and unit-tested with
  known inputs. No implicit axis assumptions.
- **Vector floorplan:** vertices are 2D positions relative to the model center. We
  store them as-is plus an explicit `origin="model_center"` note; a helper translates
  to an absolute frame only when asked. Areas computed with shapely; when a real-world
  area is needed, project via pyproj to EPSG:32615 (Houston), consistent with the TRD.
- Every conversion has: a docstring stating input/output frames and units, and a test
  with a hand-computed expected value.

## 7. Ingestion jobs

All jobs are `async`, cache-backed, idempotent, and log structured progress.

- **backfill.py** — `paginate` model search; for each model, parse core fields + keep
  raw JSON; compare `modified` + content hash to the stored record; write only on
  change. Houston filter via geocoded address (reuse/extend geometry helpers).
- **pi.py** — only runs if `pi_available`; fetches floors/rooms/dimensions/floorplan;
  parses to models; stores under `pi/`. On any PI field error for a model, records a
  per-field note and continues (degrade gracefully).
- **assets.py** — reads asset URLs from the model record; for each configured type,
  downloads via `cache.cached_bytes`, computes sha256, writes sidecar + manifest entry;
  skips verified-complete assets on rerun. Point clouds only when configured.
- **matching.py** — geocode address → match to `properties.json`; apply `overrides.json`
  last; write `links.json` with method + confidence.

## 8. Backend API (Phase 2, `service.py` + routes)

Read-only over `data/matterport/`:

| Method | Path | Returns |
|---|---|---|
| GET | `/properties` | paginated list; filters `q`, `location`, `min_sqft`, `max_sqft`, `min_rooms`, `max_rooms` |
| GET | `/properties/{id}` | one property + floors/rooms/dimensions |
| GET | `/properties/{id}/assets` | asset URLs + embed/share URLs |

Pydantic request/response models; structured logging; OpenAPI via FastAPI.

## 9. Front end (Phase 3)

Reuse the existing `frontend/` React app conventions (Vite, routes). New routes:
`/properties` (list + search + thumbnails) and `/properties/:id` (Showcase iframe +
Matterport SDK tags/navigation + side panel with dimensions, total area, and a 2D
floorplan redrawn from vector data on a `<canvas>`/SVG). glTF Three.js viewer behind
`mp_enable_gltf_viewer`.

## 10. Testing

- Unit: client retry/backoff/pagination (mock transport), parsers (fixture JSON →
  models), coordinate conversions (hand-computed expectations).
- Integration: full ingest of a few models from recorded cache entries, `CACHE_MODE=read_only`,
  network disabled — asserts stored JSON is stable across two runs (idempotency).
- No live Matterport calls in CI.

## 11. Open risks / to verify against Matterport docs

- Exact schema (resolved by R1 before any ingestion code is finalized).
- Whether PI is on our plan (resolved by R1 report).
- Webhook signature scheme (R6) — must be confirmed from Matterport docs; not guessed.
- Asset URL fields and whether OBJ/point cloud are exposed to our token (resolved by R1
  + first asset fetch).
