# Matterport 3D Property Data Platform — Tasks

Implements `design.md`. Do tasks in order; each cites the requirement(s) it satisfies.
Tasks marked **[GATE]** stop for user confirmation before proceeding.

## Phase 0 — Scaffolding & secrets

- [ ] 0.1 Add Matterport settings to `app/config.py` (`mp_token_id`, `mp_token_secret`,
  `mp_api_url`, retry/backoff, `mp_asset_types`, feature flags). Ensure the secret is
  never logged. _(R2, R10.2)_
- [ ] 0.2 Add `.env.example` with `MP_TOKEN_ID` / `MP_TOKEN_SECRET` placeholders and the
  other MP_* vars; confirm `backend/.env` is gitignored. _(R10.2)_
- [ ] 0.3 Create `app/matterport/` package with empty module stubs per design §1.

## Phase 1a — API client + introspection  (deliverable gate 2)

- [ ] 1.1 Implement `client.py`: basic auth, async httpx, `graphql()` through
  `cache.cached`, retry/backoff with jitter, `Retry-After`, GraphQL-error detection,
  secret redaction. _(R2.1–R2.3, R2.5, R2.6)_
- [ ] 1.2 Implement `paginate()` over `nextOffset`/`totalResults`. _(R2.4)_
- [ ] 1.3 Unit tests for client retry/backoff/pagination with a mock transport
  (no network). _(R10.3)_
- [ ] 1.4 Implement `schema.py`: run GraphQL introspection, save
  `data/matterport/schema.json`, generate `schema-report.md` + stdout summary,
  detect `pi_available`. Script: `scripts/mp_introspect.py`. _(R1)_
- [ ] **1.5 [GATE]** Run introspection against the live API; show the user the
  capability report (query roots, Model fields, pagination fields, PI availability)
  and the **proposed Pydantic data model**. Get explicit confirmation before Phase 1b.
  _(R1, deliverable gate 3)_

## Phase 1b — Models, queries, parsers  (after gate 1.5)

- [ ] 1.6 Write `queries.py` (GraphQL docs) and `models.py` (Pydantic) from the
  confirmed schema — no guessing. _(R2, R3)_
- [ ] 1.7 Implement `parsers.py`: raw model JSON → `models.py`; PI parsing with
  per-field graceful degradation. Unit tests on fixture JSON. _(R3, R4, R10.3)_
- [ ] 1.8 Implement `geometry.py`: Z-up handling + vector-floorplan (model-center)
  conversions, documented and unit-tested with hand-computed values. _(R4.3, R5.5, R10.3)_

## Phase 1c — Thin vertical slice  (deliverable gate 4)

- [ ] 1.9 Implement `storage.py` (local disk + checksum; interface for future S3). _(R5.4)_
- [ ] 1.10 Implement `backfill.py` limited to 5–10 Houston models; store core fields +
  raw JSON atomically; idempotent. _(R3)_
- [ ] 1.11 Implement `assets.py` for mesh + images on those models (point clouds off);
  checksums, manifest, resumable/idempotent. _(R5)_
- [ ] 1.12 If `pi_available`: `pi.py` for those models; else record `pi_available=false`. _(R4)_
- [ ] 1.13 Minimal read endpoints + a detail page that displays one ingested model
  (Showcase embed + stored fields). Verify the slice end to end. _(R8 subset, R9 subset)_
- [ ] **1.14 [GATE]** Show the user the ingested slice on a detail page; confirm before
  scaling to the full Houston portfolio.

## Phase 1d — Scale ingestion

- [ ] 1.15 Full Houston backfill (all models, idempotent diffing). _(R3)_
- [ ] 1.16 Full PI ingestion if available. _(R4)_
- [ ] 1.17 Full asset downloader run (configurable types). _(R5)_
- [ ] 1.18 `matching.py`: geocode + link + overrides + confidence. _(R7)_
- [ ] 1.19 Integration test: offline (`read_only`) ingest of recorded models is stable
  across two runs. _(R10.1, R10.3)_

## Phase 2 — Backend API

- [ ] 2.1 `service.py` read layer over `data/matterport/`. _(R8)_
- [ ] 2.2 Routes: list/search properties (filters + pagination), get one with
  rooms/floors/dimensions, get assets/embed URLs; Pydantic validation; structured
  logging; OpenAPI. _(R8)_
- [ ] 2.3 API tests with recorded fixtures. _(R10.3)_

## Phase 3 — Front end

- [ ] 3.1 Property list: thumbnails + search. _(R9.1)_
- [ ] 3.2 Property detail: Showcase iframe + Matterport SDK tags/navigation. _(R9.2)_
- [ ] 3.3 Side panel: room dimensions, total area, 2D floorplan redrawn from vectors. _(R9.3)_
- [ ] 3.4 (flag) Three.js glTF viewer from OBJ→glTF. _(R9.4)_

## Phase 4 — Incremental sync (feature-flagged)

- [ ] 4.1 Verify Matterport's webhook payload + signature scheme from their docs. If
  unverifiable, STOP and report rather than guess. _(R6.1)_
- [ ] 4.2 Webhook receiver with verified signature check. _(R6.1)_
- [ ] 4.3 Scheduled reconciliation fallback. _(R6.2, R6.3)_

## Cross-cutting

- [ ] X.1 README: setup, env vars, run the backfill, add new fields, and the CoStar/
  Matterport data-use note + usage restrictions. _(R10.4)_
