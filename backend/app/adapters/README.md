# Toolkit discovery (T0.3)

Discovered from the CoStar kit at `COSTAR_KIT_DIR` (default `~/costar-kit`), by `scripts/explore_toolkit.py`.
Kit files are read in place and never copied into the repo.

## Summary

| Layer | Access | Status |
|---|---|---|
| CoStar records | Local JSON Lines files in the kit. **No API.** `schemas/openapi.yaml` has `paths: {}` (record shapes only) | ✅ working, cached |
| CoStar photos (incl. aerials) | `attachmentUri` on CoStar's CDN (`ahprd1cdn.csgpimgs.com`) | ❌ plain GET returns **403 Forbidden** |
| Matterport model ids | `commercial-properties.csv` `MatterportModelId`, also `attachments[].videoKey` in the record | ✅ working, cached |
| Matterport API (panos, rooms, MatterPak) | "provided in a separate zip file" (kit `index.md`) | ❌ zip not received |
| Vexcel overhead / oblique | Not mentioned anywhere in the kit | ❌ no docs / endpoints |

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
| Overhead image | `costar.attachment` (CoStar aerial as stand-in) | ❌ CDN 403 |
| Oblique ×4 | — | ❌ no Vexcel access |

## Open questions for the human

1. Vexcel: docs / base URL / auth for overhead + oblique (key `VEXCEL_API_KEY` is set but nothing describes the API).
2. Matterport: the "separate zip" with connection details (`MATTERPORT_API_KEY` / `MATTERPORT_API_TOKEN` are set).
3. CoStar CDN images return 403 to a plain request. Are they meant to be fetchable from our server, and how?
