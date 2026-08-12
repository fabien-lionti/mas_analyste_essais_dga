from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app_v2.app.api.routes import analyses, annotations, channels, dynamic_analysis, exploration, files, resampling


app = FastAPI(title="Analyse Essais DGA")
STATIC_DIR = Path(__file__).resolve().parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(analyses.router)
app.include_router(files.router)
app.include_router(channels.router)
app.include_router(resampling.router)
app.include_router(exploration.router)
app.include_router(annotations.router)
app.include_router(dynamic_analysis.router)


@app.get("/")
def root():
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(
        index_path.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/api/status")
def api_status():
    return {
        "name": "Analyse Essais DGA",
        "status": "ok",
        "architecture": "analysis-centric",
    }
