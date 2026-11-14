#!/usr/bin/env bash
# Start the API.   scripts/run_server.sh          -> uses .env as is
#                  scripts/run_server.sh demo     -> CACHE_MODE=read_only (offline; a cache miss is an error)
# Env: HOST (default 127.0.0.1; use 0.0.0.0 only without a reverse proxy), PORT (8000), PYTHON (python3).
# One worker on purpose: the quant engine and the replan lock keep state in process memory.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "backend/.env missing: copy .env.example and fill in the keys" >&2; exit 1; }
if [ "${1:-}" = "demo" ]; then export CACHE_MODE=read_only; echo "demo mode: CACHE_MODE=read_only" >&2; fi
exec "${PYTHON:-python3}" -m uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}" \
  --workers 1 --proxy-headers --forwarded-allow-ips="127.0.0.1"
