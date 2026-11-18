"""API de SnapReverse. Ejecuta: .venv/bin/uvicorn backend.main:app --reload"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.snapreverse.api import router
from backend.snapreverse.service import svc


@asynccontextmanager
async def lifespan(_: FastAPI):
    svc.start()  # calcula métricas en un hilo; /health responde de inmediato
    yield


app = FastAPI(title="SnapReverse — Hackathon NFL UNAM", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# En producción el servidor sirve el build del dashboard en la misma URL.
_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="dashboard")
