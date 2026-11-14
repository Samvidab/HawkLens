# Deploying the API to a Vultr instance (prep only; nothing here has been run on a server)

**Instance:** Ubuntu 24.04, 2 vCPU / 4 GB is plenty (Gemini and the stub engine do the heavy lifting). Open ports 22, 80, 443 only.
**Rule:** one uvicorn worker (`--workers 1`): the engine cache and the action lock live in process memory.

## 1. Server setup
```bash
apt update && apt install -y python3.11 python3.11-venv git rsync caddy ufw
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw --force enable
useradd -m -s /bin/bash retro && mkdir -p /opt/retroalpha && chown retro: /opt/retroalpha
sudo -u retro git clone <repo-url> /opt/retroalpha && cd /opt/retroalpha && git checkout <branch-or-tag>   # main or tag `demo`
cd backend && sudo -u retro python3.11 -m venv .venv && sudo -u retro .venv/bin/pip install -r requirements.txt
```
`ENGINE_MODE=live` (the real quant engine) needs numpy and `pulp[cbc]` (both pinned in requirements.txt). If the optimizer cannot find a solver (`pulp.listSolvers(onlyAvailable=True)` is empty), `apt install coinor-cbc`.

## 2. Secrets and data (from your laptop; never via git)
```bash
scp backend/.env retro@SERVER:/opt/retroalpha/backend/.env          # then edit: CORS_ORIGINS, CACHE_MODE, ENGINE_MODE
rsync -a backend/cache/ retro@SERVER:/opt/retroalpha/backend/cache/ # warmed toolkit + Gemini responses (incl. media/mesh)
rsync -a backend/data/  retro@SERVER:/opt/retroalpha/backend/data/  # portfolio.json, buildings/*, plans, runs
```
Start from `backend/.env.example`. For judging use `CACHE_MODE=read_only` (a cache miss is an error, no network calls), `ENGINE_MODE` and
`NESSIE_MODE` as agreed with their owners. Set `CORS_ORIGINS=https://<your frontend domain>` (comma separated, no trailing slash;
`CORS_ORIGIN_REGEX` for Vercel previews).

**Gemini on Vertex AI:** `.env` has `GOOGLE_GENAI_USE_VERTEXAI=true` and `VERTEX_API_KEY` (copy the same `.env` to the server; that is all it
needs). Without a `VERTEX_API_KEY` it falls back to Application Default Credentials (`GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_LOCATION`; on a
server that means a service-account key file in `GOOGLE_APPLICATION_CREDENTIALS`). With the flag off it uses the AI Studio `GEMINI_API_KEY`
(HTTP 402 there means the prepaid credit is spent). A cache-only demo (`CACHE_MODE=read_only`) needs no credentials at all.

## 3. Run
```bash
cp /opt/retroalpha/backend/deploy/retroalpha.service /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now retroalpha
# HTTPS reverse proxy (edit the domain; point its DNS A record at the server first)
cp /opt/retroalpha/backend/deploy/Caddyfile /etc/caddy/Caddyfile && systemctl reload caddy
```
Quick manual run instead of systemd: `scripts/run_server.sh` (or `scripts/run_server.sh demo` for read-only cache).

## 4. Check
```bash
curl https://api.YOURDOMAIN.com/health                      # status ok + modes
curl https://api.YOURDOMAIN.com/registry | head -c 200
cd /opt/retroalpha/backend && .venv/bin/python scripts/smoke_test.py --url https://api.YOURDOMAIN.com   # goal -> events -> every action
curl -N "https://api.YOURDOMAIN.com/events/<run_id>?replay=1"   # paced replay of a recorded run
journalctl -u retroalpha -f                                  # logs
```
From the frontend origin the browser must show no CORS errors (also on the SSE stream).

## 5. Update / rollback
`cd /opt/retroalpha && sudo -u retro git pull && systemctl restart retroalpha` (rollback: `git checkout <previous tag>`). Never update in the hour before judging.

## Notes
- Keys live only in `.env` on the server (mode 600). Never commit `.env`, `cache/` or `data/` (except `data/portfolio.json`).
- If Gemini rate-limits: `MAX_CONCURRENT_BUILDINGS=2` and demo from the cache.
- Nessie writes only happen after an `approve` action with the current `plan_id`; in stub mode nothing leaves the server.
