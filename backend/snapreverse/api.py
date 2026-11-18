"""Endpoints /api/*."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from .config import CFG
from .data_access import clean
from .service import svc

router = APIRouter(prefix="/api")


def _ready():
    if svc.error:
        raise HTTPException(500, f"Error cargando datos: {svc.error}")
    if not svc.ready:
        raise HTTPException(503, "Calculando métricas al arrancar; reintenta en unos segundos.")


def _ok(o):
    return JSONResponse(clean(o))


def _mode(m: str) -> str:
    if m not in ("retro", "live"):
        raise HTTPException(422, "mode debe ser 'retro' o 'live'")
    return m


@router.get("/status")
def status():
    return _ok(svc.status())


@router.get("/config")
def config():
    return _ok({"config": CFG.__dict__, "metric": {
        "name": "SnapReverse — Índice de Explosividad Relativa",
        "definition": "100 × rapidez media (yd/s) 0–1.0 s tras el snap ÷ mediana propia del defensivo (rol Pass Rush, contexto comparable).",
        "meaning": "100 = su propia referencia; 80 = 80% de esa medida de referencia, no 80% de capacidad fisiológica.",
        "limits": ["No mide energía ni fatiga ni lesiones.", "No predice si una rotación mejora el resultado.",
                   "Participación y descanso reales no están verificados."]}})


@router.get("/demo-case")
def demo_case():
    _ready()
    if not svc.demo:
        raise HTTPException(404, "Sin caso demo")
    return _ok(svc.demo)


@router.get("/games")
def games():
    _ready()
    return _ok(svc.games())


@router.get("/games/{game_id}/teams/{team}/players")
def players(game_id: int, team: str):
    _ready()
    r = svc.players(game_id, team.upper())
    if r is None:
        raise HTTPException(404, "Partido/equipo sin intervenciones observadas")
    return _ok(r)


@router.get("/players/{nfl_id}/games/{game_id}/series")
def series(nfl_id: int, game_id: int, mode: str = Query("retro")):
    _ready()
    s = svc.series(nfl_id, game_id, _mode(mode))
    if s is None:
        raise HTTPException(404, "Sin intervenciones de ese jugador en ese partido")
    return _ok(s)


@router.get("/players/{nfl_id}/games/{game_id}/sensitivity")
def sensitivity(nfl_id: int, game_id: int):
    _ready()
    s = svc.sensitivity(nfl_id, game_id)
    if s is None:
        raise HTTPException(404, "Sin intervenciones de ese jugador en ese partido")
    return _ok(s)


@router.get("/replay")
def replay(gameId: int, playId: int, nflId: int):
    _ready()
    try:
        r = svc.replay(gameId, playId, nflId)
    except Exception:
        raise HTTPException(404, "Sin tracking para ese partido")
    if r is None:
        raise HTTPException(404, "Jugada inexistente")
    return _ok(r)


@router.get("/compare")
def compare(nflId: int, gameId: int, playId: int, refGameId: int | None = None, refPlayId: int | None = None, mode: str = "retro"):
    _ready()
    if (refGameId is None) != (refPlayId is None):
        raise HTTPException(422, "refGameId y refPlayId van juntos")
    try:
        r = svc.compare(nflId, gameId, playId, refGameId, refPlayId, _mode(mode))
    except StopIteration:
        r = None
    if r is None:
        raise HTTPException(404, "Intervención inexistente")
    if r.get("error"):
        raise HTTPException(422, r["message"])
    return _ok(r)
