"""Endpoints /api/ai/*. Bedrock solo se usa desde el backend."""
from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..api import _ready
from ..data_access import clean
from ..service import svc
from . import agent
from .bedrock import AIUnavailable, bedrock
from .schemas import AnalyzeIn, ChatIn, CompareIn
from .tools import ToolError

router = APIRouter(prefix="/api/ai")


def _guard(nfl_id: int, game_id: int):
    _ready()
    if not ((svc.df.nflId == nfl_id) & (svc.df.gameId == game_id)).any():
        raise HTTPException(404, "Sin intervenciones de ese jugador en ese partido")


def _unavailable(e: AIUnavailable):
    code = 429 if e.code in ("budget", "rate_limit", "ThrottlingException") else 503
    return JSONResponse({"ok": False, "ai_available": False, "code": e.code, "detail": e.message}, status_code=code)


@router.get("/status")
def status():
    return JSONResponse(clean({"ok": True, "enabled": True, "note": "No se verifica AWS en este endpoint; los errores aparecen al analizar.", **bedrock.status()}))


@router.post("/analyze-player")
def analyze(body: AnalyzeIn):
    _guard(body.nflId, body.gameId)
    try:
        return JSONResponse(agent.analyze_player(svc, body.nflId, body.gameId, body.mode, body.refresh))
    except AIUnavailable as e:
        return _unavailable(e)
    except ToolError as e:
        raise HTTPException(422, str(e))


@router.post("/chat")
def chat(body: ChatIn):
    _guard(body.nflId, body.gameId)
    try:
        return JSONResponse(agent.chat(svc, body.nflId, body.gameId, body.mode, body.message, [t.model_dump() for t in body.history],
                                       {"playId_seleccionada": body.playId, "playId_referencia": body.refPlayId}))
    except AIUnavailable as e:
        return _unavailable(e)


@router.post("/compare-plays")
def compare(body: CompareIn):
    _guard(body.nflId, body.gameId)
    try:
        return JSONResponse(agent.explain_compare(svc, body.nflId, body.gameId, body.mode, body.playId, body.refGameId, body.refPlayId))
    except AIUnavailable as e:
        return _unavailable(e)
    except ToolError as e:
        raise HTTPException(422, str(e))
