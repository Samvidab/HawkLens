from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.matterport.routes import router as matterport_router

app = FastAPI(title="RetroAlpha backend")

# Allow the local Vite dev server to call the API during development.
app.add_middleware(
    CORSMiddleware,
    # Any localhost port during development (Vite picks 5173+ depending on what's free).
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matterport_router)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "cache_mode": s.cache_mode,
        "engine_mode": s.engine_mode,
        "nessie_mode": s.nessie_mode,
        "demo_city": s.demo_city,
    }
