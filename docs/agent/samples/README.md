# Sample layouts for the frontend

Real output of the backend pipeline (site-engineer rules → stub engine → replan → composer → resolver) on a
**synthetic** four-building Houston portfolio ("Sample Tower", "Sample Plaza", "Sample Lofts", "Sample
Annex"). Props are fully resolved, exactly what `POST /compose` returns. Not CoStar data. Pricing comes from
the stub engine, so `plan_table.props.sample_pricing` is `true` (show the "sample pricing" badge).

| File | Situation | How it was produced |
|---|---|---|
| `portfolio_overview.json` | `portfolio_overview` | `goal` {target 25 %} |
| `target_gap.json` | `target_gap` | `goal` {target 90 %, budget $400k} → engine says infeasible |
| `verification_issue.json` | `verification_issue` | `goal`, one rejected claim backing an upgrade (evidence_gallery shows it first with the verifier note) |
| `building_detail.json` | `building_detail` | `open_building` {b1}: hero with Matterport (`hero_3d`, `floor_plan`, pins) |
| `building_detail_showcase.json` | `building_detail` | same, but Lane A supplied a Matterport tour link (`showcase_url`): `hero_3d.props.mode` = `"showcase"`, mesh urls are `null` |
| `building_detail_no_matterport.json` | `building_detail` | `open_building` {b3}: no mesh, no showcase link and no interior data → `portfolio_3d` instead, no `hero_3d`/`floor_plan` |
| `approved.json` | `approved` | `approve` {plan_id} → financing_card executed (stub Nessie ids), memo, plan_table |
| `registry.json` | – | `GET /registry`: JSON Schema of every widget's props, default size, and the actions it emits |

## Contract notes
- Layout: `{layout_id, run_id, situation, focus_building_id, generated_at, widgets[]}`; widget = `{id, type, title, why, size, data_ref, props}`.
  Grid is 12 columns: `full`=12, `wide`=8, `half`=6, `side`=4. At most 8 widgets; `activity_feed` is always last, `side`, and its
  only prop is `run_id` (open `GET /events/{run_id}` SSE yourself). `why` is ≤ 90 chars (here the stock lines; in a live run Gemini may rewrite them).
- Props never contain free text from an LLM except `why` and `memo.markdown` (numbers in both are substituted/checked by code).
- Optional numbers can be `null` (e.g. `p_hit_target` before a plan exists, `upfront_usd` if the engine omits it): render a dash.
- `hero_3d` appears only when the building has a mesh or a showcase link; `floor_plan` only when it has interior room data (rooms may have an empty `polygon`: list them with areas). `hero_3d.props.mode`: `"mesh"` (render `mesh_url`/`mtl_url`) or `"showcase"` (embed `showcase_url` in an iframe; mesh urls are null, pins informational).
- Images: `evidence_gallery.items[].url` = `/media/{image_id}`; marks are normalized 0–1 (`bbox` = x0,y0,x1,y1, or `polygon`).
  Mesh: `hero_3d.props.mesh_url` / `mtl_url` = `/media/mesh/{model_id}/model.obj|.mtl`; textures load relative to that folder.
  These sample URLs are illustrative (no files behind them here).
- `portfolio_3d.buildings[].overlays`: `solar` and `cool_roof` carry `polygon_wkt` (WGS84, lon/lat), `window` carries `facade` (N/E/S/W).
  `roof_texture_url` is `null` until an overhead image is registered for the building.
- Actions come back as `POST /compose` bodies `{run_id, type, payload}`; the widgets that emit them are listed per widget in `registry.json` (`emits`).
  `approve` needs `payload.plan_id` equal to `financing_card.props.plan_id`.

Regenerate (deterministic, no keys or network): `cd backend && python scripts/make_samples.py`.
`tests/test_samples.py` fails if these files go stale or stop validating.
