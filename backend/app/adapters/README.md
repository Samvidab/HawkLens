# Toolkit discovery (T0.3)

Discovered from the CoStar kit at `COSTAR_KIT_DIR` (default `~/costar-kit`), by `scripts/explore_toolkit.py`.
Kit files are read in place and never copied into the repo.

## Summary

| Layer | Access | Status |
|---|---|---|
| CoStar records | Local JSON Lines files in the kit. **No API.** `schemas/openapi.yaml` has `paths: {}` (record shapes only) | ✅ `costar.py`, cached |
| CoStar photos (incl. aerials) | `attachmentUri` on CoStar's CDN | ⛔ 403; **skipped by decision** (Vexcel covers aerials) |
| Matterport model ids | `commercial-properties.csv` `MatterportModelId`, also `attachments[].videoKey` in the record | ✅ `costar.matterport_model_ids` |
| Matterport Model API | GraphQL, `POST https://api.matterport.com/api/models/graph`, basic auth `MATTERPORT_API_KEY`:`MATTERPORT_API_TOKEN` (production only) | ✅ `matterport.py`, live-tested |
| Vexcel overhead | `POST https://api.vexcelgroup.com/v2/ortho/extract`, `X-API-KEY` header; body → JPEG | ✅ `vexcel.overhead`, live-tested on all 8 portfolio buildings |
| Vexcel oblique / roof attributes | Documented only in the Vexcel quickstart that should be in `backend/toolkit/` | ❌ `backend/toolkit/` not in the merge; `vexcel.oblique` raises `NotImplementedError` |

Sources: `docs/agent/costar-quickstart.md` (Matterport sections 1–8, Vexcel section 7).

## Matterport Model API (real queries, `matterport.py`)

| Function | Query | Notes |
|---|---|---|
| `key_check()` | `rootFolder { name modelCountSummary(includeModelsInSubfolders: true) }` | "HackPrinceton 2026", 14,944 models |
| `basics(id)` | `model(id) { id name description created visibility address{…} geolocation{lat long} generatedDescription{summary} propertyClassifications{…} floors{id label} rooms{id} panoLocations{id} image{url} }` | lat/long come back as strings |
| `panoramas(id)` | `panoLocations { id label position{x y z} skybox(resolution: "2k") { status children } }`, `view(type: "matterport.model.defurnished") { id }` | 6 faces: 0 up, 1–4 horizon, 5 down. Signed URLs expire → `pano_face()` downloads to cache and re-queries once on 401/403 |
| `rooms(id)` | `floors { vertices{id position{x y}} edges{id type thickness vertices{id}} }`, `rooms { classifications{label confidence} boundary{edges{id}} dimensions(units: metric){areaFloor width depth height} }`, `assets { floorplans(provider: "matterport") {format flags url width height resolution origin{x y}} }` | wall graph in metres, model frame |
| `matterpak_status(id)` | `bundle(id: "mp:matterpak") { availability }`, `assets { resources(format: "matterpak") { status filename url } }` | `unlocked` / `locked` |
| `matterpak(id)` | (above, then download zip) | extracts OBJ/MTL/textures/colorplan into `cache/media/mesh/<id>/`; `cloud.xyz` (≈400 MB) only with `include_pointcloud=True` |

The Model API has no geographic search. Models are matched to buildings through the CoStar CSV (PropertyId → model ids).

## Vexcel (`vexcel.py`)

`overhead(point_wkt, buffer_m)` sends `{"wkt": <square around point>, "srid": 4326, "layer": "urban,urban-r,wide-area,urban-g", "crop": "bounding_box", "image-format": "jpeg", "destination-dimensions": "1400,1400", "attribution": "false"}`. Native GSD is 7.5 cm; `gsd_m` on the ImageRef is the effective `2·buffer/1400`. `overhead_buffer_m(rba, stories)` sizes the crop to ~2.2× the estimated footprint side. Houston and LA only (403 elsewhere).

## CoStar kit layout

| Path | Use |
|---|---|
| `data/commercial-property.jsonl` | 3,339 records, one per line (193 MB). **Stream it**; never load whole |
| `commercial-properties.csv` | `PropertyId, MatterportModelId, Address, City, State`; 13,147 rows (one per property × model); 51 properties have an empty model id |
| `models/commercial-property.md` | Field meanings + enum tables |
| `schemas/commercial-property.schema.json` | JSON Schema 2020-12; 55 top-level properties, no `required` |
| `schemas/enums.json` | Integer enum → name |

There is **no `models_index.csv`** in the kit. The CSV already carries `MatterportModelId`.
Join: CSV `PropertyId` = JSONL `id`. Model id also = `attachments[].videoKey` where `videoExternalReferenceType ∈ {36 MatterportScan, 234 MatterportStreamingKey}`. Verified equal for 23347.

City in the CSV is not normalized (`Houston`, `houston`, `Los Angeles`, `LOS ANGELES`). Use `primaryAddress.researchMarketId` instead: **14 = Houston, 20 = Los Angeles**.

## CoStar record → BuildingProfile fields (real names)

| BuildingProfile | CoStar field | Notes |
|---|---|---|
| `costar_id` | `id` | int |
| `name` | `buildingName` | nullable → fall back to street address |
| `address` | `primaryAddress.{streetNumber, streetDirection, streetName, streetType, streetSuffix}`, `city`, `state`, `postcode` | |
| `city` | `primaryAddress.researchMarketId` | 14 Houston, 20 Los Angeles |
| `lat`, `lon` | `primaryAddress.latitude`, `primaryAddress.longitude` | present on all 3,339 |
| `footprint_wkt` | **none**. No building footprint in the record (only `propertyRetail/land.frontage[].footprint.shape` LineStrings) | always `estimated` from `geometry.footprint_polygon` |
| `property_type` | `propertyType` (int) | 1 Hospitality, 2 Industrial, 3 Land, 5 Office, 6 GeneralRetail, 7 Flex, 9 MixedUse, 10 Specialty, 11 Multifamily, 13 Healthcare, 15 Residential, 16 Homes |
| `building_class` | `buildingClass` | 0 Unknown, 1 A, 2 B, 3 C, 4 F |
| `year_built` | `constructionEvents[]` with `eventType == 2` (ConstructionComplete) → `year` | |
| `stories` | `numStoriesAboveGrade` | |
| `rba_sqft` | `rentableBuildingAreaSquareFeet` | also `grossBuildingAreaSquareFeet`, `grossTypicalFloorSquareFeet` (use typical floor for footprint estimate) |
| `occupancy_pct` | **not in the property record** | would need `location-occupancy.jsonl`; leave null |
| `matterport_model_id` | CSV `MatterportModelId` / `attachments[].videoKey` | a property can have several |

Useful extras: `buildingHeightInFeet`, `buildingConstructionMaterial`, `renovations[].renovationImprovementTypes` (6 HVAC, 8 Roof, 5 Façade), `environmental.leedCertifications[]`, `floors[].floorSize.squareFeet`, `constructionStatus` (1 = Existing).

Attachments (`attachments[]`): `attachmentType` 1 Aerial, 3 PrimaryPhoto, 4 BuildingPhoto, 10 FloorPlan, 33 InteriorPhoto, 43 Matterport3DScan. `attachmentUri` has a `/112/` size segment (other sizes: 102, 104, 110, 111, 113, 114, 116). 2,317 of 3,339 properties have an aerial attachment with a URI.

## Demo-city inventory (Houston, `DEMO_CITY`)

Houston (market 14): 1,348 multifamily, 191 office, 98 industrial, 54 hospitality, 41 retail, 21 flex.
LA (market 20): 1,417 multifamily, 98 office, 24 industrial, 24 retail.

## Sample pulls (cached under `backend/cache/`)

Sample: **PropertyId 23347, "333 Northbelt"**, 333 Sam Houston Pky, Houston. Office, class B, 12 stories, RBA 213,281 sf, built 1980, 29.9407608 / -95.3982479.

| Pull | Cache namespace | Result |
|---|---|---|
| CoStar record | `costar.property` | ✅ (read_only re-run hits cache) |
| Matterport model list | `costar.matterport_models` | ✅ 5 models: `NLpW1UAp1HJ, NgGvLZnbEMM, VKkfYGTqZAx, WSYTQt3istC, w63JtBJm3gt` |
| Overhead image | `vexcel.ortho` | ✅ all 8 portfolio buildings (e.g. hero 23551 at 8.6 cm/px) |
| Oblique ×4 | — | ❌ oblique API undocumented in what we have |
| MatterPak availability (hero 23551) | `matterport.matterpak` | ✅ all 10 models `unlocked`; hero model `hu9LX64osUN` (Suite 266, 17 panos, 3 rooms) |

## Open items

1. Vexcel obliques + roof attributes: need the Vexcel quickstart (`backend/toolkit/` did not come through the merge). Aerial inspector runs overhead-only until then (plan fallback "skip obliques").
2. `models_index.csv` (splat models) also missing; not needed since the hero's MatterPak is unlocked.
