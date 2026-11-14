# Lane A (critical path), branch `lane-data`

Phase 1 done (AC-1). Phase 2: T2.1 done live; T2.2 and T2.3 code + tests done, **live runs blocked on Gemini daily quota**.

## Done
- T0.1, T0.2 (before this session)
- T0.3/T0.4 (`f5a16ce`, `d711f9f`, `0a1e311`): `adapters/README.md`; `costar.py`, `matterport.py`, `vexcel.py` (overhead), `types.py`. Live test (`-m live`) passes.
- T1.1 (`a51e025`, `0a1e311`): `data/portfolio.json`, 8 Houston offices, all with Vexcel overhead. Hero 23551 Harwin Plaza II, model `hu9LX64osUN` (17 panos, 3 rooms).
- T1.5 (`93f652f`) records agent · T1.6 (`dc629c7`) aerial inspector · T1.8 (`bbcffd3`) `survey_one.py`, **AC-1 passes**.
- T2.1 (`dff900c`): `agents/graph.py` (orchestrator plan → `Send` fan-out → survey subgraph [records → aerial ∥ interior → site engineer → verify ⟲ reinspect → finalize] → collect), `main.py` (`POST /run`, `GET /state/{id}`, SSE events router, `/portfolio`, `/registry`, `/media/{id}`, `/media/mesh/{model}/{file}`). **Live: run_8e9dd656 surveyed 8/8 buildings, 4 at a time, 23 feasible upgrades, events streamed over SSE.** That run was `CACHE_MODE=read_write`: records, Vexcel imagery and aerial Gemini calls for all 8 are cached.
- T2.2 (code + tests): `agents/verifier.py` + `prompts/verifier.md`. One batched Gemini call per building per inspector per round; ≥0.7 verified, <0.3 rejected, else sent back with a number-checked question (≤2 loops) then unverified; unknown values → unverified; verifier errors → unverified, never a send-back. Batched `aerial.reinspect`. `verification.json` per building. Tests drive the real subgraph through every outcome incl. 3 `send_back` events.
- T2.3 (code + tests): `agents/interior.py` + `prompts/interior.md`. 5 panoramas (farthest-point sampled, ceiling + 2 horizon faces), lighting / HVAC / window claims, pins at scan xyz, `interior.json` + `interior_scan.json`, batched reinspect, MatterPak download when available.
- `llm.py` (Lane B's file, small change): waits out 429s using the API's `retryDelay`, optional `GEMINI_RPM` pacing, fails fast with `QuotaExhausted` when the API asks for > 90 s (daily cap).

- Merge of `agent` (`41b48e4`, `3ecc10e`, `35eb598`): conflicts in llm.py / main.py were NOT pre-resolved on `agent`; resolved here keeping both sides. main.py = Lane B's (media router, /compose, /state) + `POST /run` (survey → Lane B goal replan: pricing → compose → `done`); `graph.survey_runner` registered with replan. llm.py = Lane B's model fallback + my 429 waits / `GEMINI_RPM` / `QuotaExhausted`. Survey completion is now a `decide` event; `done` comes after compose.
- **Live after merge (run_43e96f50):** 8/8 surveyed → pricing (stub engine) → composer → `done`; `/state` has layout `portfolio_overview` (7 widgets) + results; `/compose open_building` → `building_detail`; `/health`, `/portfolio`, `/registry`, `/media/{id}` all 200. Verifier hit the spent daily quota and failed fast (no hang, no false send_back). Interior failed on an expired skybox link (410) → re-sign fixed (`35eb598`), 15 faces now download live.

## Blocked / open
- **Gemini free tier: 20 requests/day per model** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `gemini-3.6-flash` spent; also 5/min). Blocks: live verifier run (genuine send_back), live interior run on the hero, cache warm-up with verifier + interior, and any re-run. Needs billing on the key or a paid key.
- **No genuine live send_back yet.** The send_backs in run t22-live were caused by 429 errors being scored as doubt (bug, fixed). Proven only in tests so far.
- **MatterPak not downloadable**: every portfolio model (37, incl. hero's 10) has `bundle availability: unlocked` but all resources `unavailable`, no URL. Mesh route is ready; hero_3d needs CoStar to generate/unlock the files, or `models_index.csv` to pick a splat model.
- **Hero scan is one suite** (~1,000 sf of 105,717 sf, 3 unlabelled rooms, empty wall graph): scanned area kept in `interior_scan.json`, not used as building floor area (coverage < 50%); envelope area null → insulation not proposed.
- **For Lane B:** composer shows `hero_3d` + `floor_plan` for the hero even with no mesh (`interior_scan.json` `mesh_url: null`) and no interior.json; App Flow §6 says omit when there's no Matterport data. Also `composer.save_state` overwrites state.json (I re-merge `status`/`results` after it).
- **Vexcel obliques**: `backend/toolkit/` still not on `agent`; facades empty, no window_upgrade.

## Notes
- venv: main checkout `backend/.venv` (Python 3.11.9). Tests: 231 pass (both lanes) + 1 live.
- Port 8765 is taken by another process; I ran the API on 8791.
- `COSTAR_KIT_DIR` added to this worktree's `backend/.env`. CoStar CDN photos (403) skipped by decision.
- Estimated footprints run ~20% under real roofs; overhead crop = 2.2× estimated side.
- `occupancy_pct` not in the CoStar property record; null.
