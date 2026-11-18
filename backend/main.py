"""API de SnapReverse. Ejecuta: .venv/bin/uvicorn backend.main:app --reload"""
import os
from contextlib import asynccontextmanager
from pathlib import Path


def cargar_env():
    f = Path(__file__).resolve().parent.parent / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env()  # antes de importar boto3

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.snapreverse.ai.api import router as ai_router
from backend.snapreverse.api import router
from backend.snapreverse.service import svc


@asynccontextmanager
async def lifespan(_: FastAPI):
    svc.start()  # calcula métricas en un hilo; /health responde de inmediato
    yield


app = FastAPI(title="SnapReverse — Hackathon NFL UNAM", lifespan=lifespan)
app.include_router(router)
app.include_router(ai_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# En producción el servidor sirve el build del dashboard en la misma URL.
_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="dashboard")
