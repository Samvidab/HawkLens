# Matterport 3D Property Data Platform — Requirements

## Context

HawkLens needs a 3D property-data platform built on the Matterport API, scoped to
**Houston**. We hold a valid Matterport API token (ID + secret) and have CoStar's
permission to use all data reachable through that token.

This platform is implemented **inside the existing RetroAlpha backend**
(`backend/`, FastAPI + Pydantic v2 + httpx) and follows its conventions:

- Every external call goes through `app/adapters/cache.py`
  (`CACHE_MODE=off|read_write|read_only`). Recorded cache entries are the CI
  fixtures; the demo runs with `read_only` and no network.
- **No relational database.** State is JSON files under `backend/data/`, written
  atomically. Binary assets live under `backend/cache/media/` with checksum sidecars
  and a manifest in `data/`. A storage interface keeps a future object store (S3/GCS)
  a drop-in replacement. (Decision confirmed with the user; deviates from the generic
  "object storage" wording in the brief for repo consistency.)
- Geometry uses shapely + pyproj. Houston projects to **UTM EPSG:32615**.
- Secrets come from env only: **`MP_TOKEN_ID`, `MP_TOKEN_SECRET`** (HTTP basic auth:
  token ID = username, secret = password). Never hardcoded, never logged.

Deltas from the original brief, agreed with the user:
- Object storage → local `cache/media` + checksums + `data/` manifest, behind a
  storage interface.
- Property/match persistence → JSON files in `data/`, not a DB.
- Webhooks and the Three.js glTF viewer are later-phase, feature-flagged; not in the
  thin vertical slice.
- Scope is Houston only.

## Terminology

- **Model** — a Matterport space (one scanned property).
- **Property record** — HawkLens's internal record a model is linked to.
- **Property Intelligence (PI)** — Matterport's floors/rooms/dimensions/vector
  floorplan data, which may require an Enterprise plan.

---

## Requirements

### R1 — Schema discovery (introspection)

**User story:** As an engineer, I want to know exactly what the Matterport GraphQL
schema exposes to *our* token, so that I never guess field names and can detect
whether Property Intelligence is available.

Acceptance criteria:
1. WHEN the introspection script is run with valid credentials THEN the system SHALL
   execute a GraphQL introspection query against `https://api.matterport.com/api/models/graph`
   and save the full schema locally (`data/matterport/schema.json`).
2. WHEN introspection completes THEN the system SHALL emit a human-readable report
   listing the query roots, the `Model` type fields, pagination fields
   (`nextOffset`, `totalResults`), and whether Property Intelligence types
   (dimensional estimates, floors, rooms, vector floorplan) are present.
3. IF credentials are missing or invalid THEN the system SHALL fail with a clear
   message and SHALL NOT print the secret.
4. The script SHALL be idempotent and re-runnable, and SHALL route the call through
   the cache adapter so CI can replay it offline.

### R2 — Typed API client

**User story:** As an engineer, I want one typed client for Matterport with retries,
backoff, rate-limit handling and pagination, so that all ingestion code is reliable
and consistent.

Acceptance criteria:
1. The client SHALL read `MP_TOKEN_ID`/`MP_TOKEN_SECRET` from settings and use HTTP
   basic auth; it SHALL never log the secret.
2. WHEN a request fails with a retryable status (429, 5xx, network error) THEN the
   client SHALL retry with exponential backoff and jitter up to a configured limit.
3. WHEN a 429 includes a `Retry-After` header THEN the client SHALL honor it.
4. The client SHALL expose a `paginate()` helper that follows `nextOffset` until
   `totalResults` is exhausted, yielding pages.
5. Every call SHALL go through `cache.cached`, keyed by operation + variables, so the
   same query returns identical results offline.
6. GraphQL errors in a 200 response SHALL be detected and raised, not silently ignored.

### R3 — Model backfill

**User story:** As a data engineer, I want to page through all Houston models and
store their core fields plus raw JSON, so that we have a complete, traceable index.

Acceptance criteria:
1. WHEN the backfill runs THEN it SHALL page through all models and store, per model:
   model ID, name, address, share/embed URLs, thumbnail image reference,
   created/modified dates, and the raw JSON response for traceability.
2. The backfill SHALL filter to Houston (by address / geocode) and record why each
   model was included or excluded.
3. The backfill SHALL be idempotent: re-running updates changed models and leaves
   unchanged ones untouched (compared by modified date + content hash).
4. Records SHALL be written atomically to `data/matterport/models/<model_id>.json`.

### R4 — Property Intelligence ingestion (graceful degradation)

**User story:** As a data engineer, I want floors/rooms/dimensions/vector-floorplan
data when our plan allows it, and clean degradation when it does not.

Acceptance criteria:
1. IF introspection (R1) found PI types THEN ingestion SHALL fetch and store floors,
   rooms (user-defined and detected labels), square footage, room dimensions, and
   vector floorplan data (edges, vertices, openings) per model.
2. IF PI types are absent THEN ingestion SHALL skip PI, record `pi_available=false`
   on the model, and continue without error.
3. Vector floorplan vertices SHALL be documented and stored as 2D positions relative
   to the model center; any coordinate conversion SHALL be explicit and unit-tested.

### R5 — Asset downloader

**User story:** As a data engineer, I want to copy model assets to our storage with
checksums, resumably and idempotently, with configurable asset types.

Acceptance criteria:
1. The downloader SHALL support meshes (OBJ), images (thumbnails + any available
   imagery), and OPTIONALLY point clouds; asset types SHALL be configurable because
   point clouds are large (default excludes point clouds).
2. Each asset SHALL be stored with a checksum sidecar; a manifest in
   `data/matterport/assets/<model_id>.json` SHALL record source URL, local path,
   size, checksum, and status.
3. WHEN interrupted and re-run THEN the downloader SHALL resume: already-complete,
   checksum-verified assets SHALL be skipped; partial downloads SHALL be re-fetched.
4. Writes SHALL go through the storage interface so a real object store can replace
   local disk without changing callers.
5. Raw mesh/point-cloud data is Z-up; this SHALL be documented, and any conversion
   SHALL be explicit and tested.

### R6 — Incremental sync (later phase, feature-flagged)

**User story:** As an operator, I want new/changed models to flow in automatically,
with a reliable fallback.

Acceptance criteria:
1. The system SHALL provide a webhook receiver whose payload parsing and signature
   verification follow **Matterport's documented webhook scheme** (to be verified
   against their docs before implementation; if unverifiable, this task stays
   unstarted and is reported, not guessed).
2. The system SHALL provide a scheduled reconciliation job that re-runs backfill
   diffing as a fallback, independent of webhooks.
3. Both paths SHALL be idempotent and converge to the same stored state.

### R7 — Property matching

**User story:** As a data engineer, I want Matterport model IDs linked to internal
property records, with geocoding and a manual override.

Acceptance criteria:
1. The system SHALL link model IDs to internal property records by address/location,
   using geocoding of model addresses.
2. The system SHALL support a manual override table
   (`data/matterport/overrides.json`) that forces or breaks specific model↔property
   links; overrides SHALL win over automatic matches.
3. Matching SHALL record a method and confidence per link and SHALL be idempotent.

### R8 — Backend API (Phase 2)

**User story:** As a frontend developer, I want HTTP endpoints to list/search
properties and fetch one with its rooms/floors/dimensions and asset/embed URLs.

Acceptance criteria:
1. The API SHALL provide: list/search properties; get one property with
   rooms/floors/dimensions; get asset and embed URLs.
2. Search SHALL filter by location, square footage, and room count.
3. All list endpoints SHALL paginate; inputs SHALL be validated (Pydantic);
   logging SHALL be structured and SHALL NOT log secrets; OpenAPI docs SHALL be
   served (FastAPI default).

### R9 — Front end (Phase 3)

**User story:** As a user, I want to browse properties and open a detail page with the
Matterport Showcase and a redrawn floorplan.

Acceptance criteria:
1. A property list SHALL show thumbnails and support search.
2. A property detail page SHALL embed the Matterport Showcase iframe and use the
   Matterport SDK for custom tags and navigation.
3. A side panel SHALL show room dimensions, total area, and a 2D floorplan redrawn
   from the vector data.
4. OPTIONAL, behind a feature flag: a Three.js viewer loading glTF converted from the
   OBJ mesh.

### R10 — Non-functional

1. Jobs SHALL be idempotent and safe to rerun.
2. Secrets SHALL come from env/secrets manager; `.env.example` SHALL exist and `.env`
   SHALL be gitignored. Secrets SHALL never be logged.
3. Unit tests SHALL cover the API client, parsers, and coordinate conversions;
   integration tests SHALL use recorded cache fixtures with **no live calls in CI**.
4. The README SHALL document setup, env vars, how to run the backfill, and how to add
   new fields; and SHALL include a data-use note stating the data is licensed from
   CoStar through Matterport, with any usage restrictions to respect.

---

## Deliverable order (gates)

1. **Spec** (this document + design + tasks). ← current
2. **Introspection script + typed API client.**
3. **Run introspection; STOP and show the user the results + proposed data model;
   get confirmation before building full ingestion.**
4. **Thin vertical slice on 5–10 models**: ingest → store → display on a detail page.
5. Scale to the full Houston portfolio; then Phase 2 API, Phase 3 front end, then the
   feature-flagged later phases (webhooks, glTF viewer).
