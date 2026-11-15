#!/usr/bin/env bash
# Backend for the Playwright tests. It can never write to the demo data dir:
#   - the demo data (DEMO_DATA_DIR, default backend/data) is COPIED to a fresh temp dir and DATA_DIR points at the copy,
#   - CACHE_MODE=read_only (a cache miss is an error; nothing is written to the cache),
#   - E2E_SANDBOX=1 makes GET /health report "sandbox": true; the Playwright guard (frontend/e2e/guard.js) refuses to run
#     tests against any backend that does not, so tests cannot be pointed at the demo backend by mistake.
# The temp copy is removed on exit.
# Env: DEMO_DATA_DIR, CACHE_DIR (the warm cache), E2E_PORT (8100), ENGINE_MODE (live), NESSIE_MODE (stub),
#      E2E_ENV_FILE (backend/.env: model names/keys for the cached calls; values are never printed), PYTHON (python3).
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${DEMO_DATA_DIR:-$PWD/data}"
[ -f "$SRC/portfolio.json" ] || { echo "e2e_backend: no portfolio.json in $SRC" >&2; exit 1; }
CACHE_IN="${CACHE_DIR:-}"  # the caller's cache dir wins over .env
TMP="$(mktemp -d "${TMPDIR:-/tmp}/hawklens-e2e.XXXXXX")"
PID=""
cleanup() { [ -n "$PID" ] && kill "$PID" 2>/dev/null; case "$TMP" in */hawklens-e2e.*) rm -rf -- "$TMP" ;; esac; }
trap cleanup EXIT
trap 'exit 143' INT TERM
# the copy: everything except recorded runs (each test run starts clean)
mkdir -p "$TMP/data"
(cd "$SRC" && tar cf - --exclude ./runs .) | (cd "$TMP/data" && tar xf -)
ENV_FILE="${E2E_ENV_FILE:-$PWD/.env}"
if [ -f "$ENV_FILE" ]; then set -a; . "$ENV_FILE"; set +a; export RETROALPHA_ENV_FILE="$ENV_FILE"; fi
export DATA_DIR="$TMP/data" CACHE_MODE=read_only E2E_SANDBOX=1
export ENGINE_MODE="${ENGINE_MODE_E2E:-live}" NESSIE_MODE=stub
[ -n "$CACHE_IN" ] && export CACHE_DIR="$CACHE_IN"
echo "e2e_backend: data copy in $TMP (removed on exit), cache read-only, port ${E2E_PORT:-8100}" >&2
"${PYTHON:-python3}" -m uvicorn app.main:app --host 127.0.0.1 --port "${E2E_PORT:-8100}" --workers 1 &
PID=$!
wait "$PID"
