# Lane A (critical path), branch `lane-data`

Tasks: T0.3 → T0.4 → T1.1 → T1.5 → T1.6 → T1.8. **All done; AC-1 passes** (Vexcel obliques pending).

## Done
- T0.1, T0.2 (before this session)
- T0.3/T0.4 (`f5a16ce`, `d711f9f`, `0a1e311`): `adapters/README.md`; `costar.py` (local kit, streamed), `matterport.py` (GraphQL: key check, basics, panos + face download, rooms, MatterPak), `vexcel.py` (ortho/extract overhead), `types.py`. Live test (`-m live`) passes.
- T1.1 (`a51e025`, `0a1e311`): `data/portfolio.json`, 8 Houston offices, all with Vexcel overhead. Hero 23551 Harwin Plaza II: all 10 MatterPaks unlocked; hero model `hu9LX64osUN` (17 panos, 3 rooms).
- Merged `agent` (Lane B schemas + costar-quickstart.md) at `30adcdf`.
- T1.5 (`93f652f`): `agents/records.py` → `profile.json` with `source_fields`, estimated footprint (typical floor plate), `fetch` event.
- T1.6 (`dc629c7`): `agents/aerial.py` + `prompts/aerial.md`: Vexcel overhead → Gemini structured observations → Claims with marks; `usable_roof_m2` in code; `aerial.json`, `claims.json`, `images.json`, `aerial_debug.png`; fallback to unknowns on LLM failure. Debug PNGs checked for 23551 and 239601.
- T1.8: `scripts/survey_one.py`. **AC-1:** 23551 → 3 upgrades (rooftop_solar 417.4 kW with Vexcel evidence, heat_pump, led_retrofit); 2nd run with `CACHE_MODE=read_only` prints identical JSON.

## In progress
- none

## Blocked / open
- **Vexcel obliques + roof attributes:** `backend/toolkit/` (Vexcel quickstart, models_index.csv, AGENTS.md, matterport_quickstart.py) was not in the `agent` branch; only `docs/agent/costar-quickstart.md` came through. `vexcel.oblique` raises NotImplementedError; facades empty, so `window_upgrade` is never proposed.
- `/media/{image_id}` route: not in my scope (main.py). Evidence files are indexed per building in `data/buildings/<id>/images.json` (image_id → local_path) for whoever adds the route.
- Solar/cool-roof upgrades stay `unverified` / `include_in_optimizer=False` until the verifier (T2.2) runs.

## Notes
- venv: main checkout `backend/.venv` (Python 3.11.9). Tests: 126 pass + 1 live.
- `COSTAR_KIT_DIR` was only in the main checkout root `.env`; added to this worktree's `backend/.env`.
- CoStar CDN photos (403): skipped by decision.
- Estimated footprints run ~20% under real roofs (hero); `usable_roof_m2` inherits that. Overhead crop = 2.2× estimated side to keep the whole roof in view.
- `occupancy_pct` not in the CoStar property record; null.
