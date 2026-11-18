"""Emparejamiento transparente de jugadas de referencia.

Criterio fijo y reproducible (NUNCA usa la rapidez para elegir, para no exagerar ni ocultar diferencias):
 filtros duros: mismo jugador, comparable (sin play action, ventana válida), mismo grupo de alineación, distinta jugada.
 modo 'live': solo jugadas ANTERIORES a la seleccionada (orden cronológico del dataset).
 ranking: menor puntaje de diferencias de contexto ponderadas; luego preferir otros partidos (historial);
          luego la más cercana en orden cronológico; luego menor (gameId, playId).
Calidad por reglas explícitas según nº de diferencias en factores clave.
"""
from __future__ import annotations

import pandas as pd

# (campo, etiqueta, peso)
FACTORS = [("pff_positionLinedUp", "Alineación exacta", 2), ("blockers", "Bloqueadores asignados", 2), ("n_rushers", "Número de rushers", 1),
           ("dist_bucket", "Distancia (corta/media/larga)", 1), ("down", "Down", 1), ("offenseFormation", "Formación ofensiva", 1),
           ("pff_passCoverageType", "Tipo de cobertura", 1), ("time_bucket", "Tiempo hasta lanzamiento/sack", 1)]


def _bucket_dist(y):
    if pd.isna(y): return None
    return "corta (≤3)" if y <= 3 else "media (4–7)" if y <= 7 else "larga (≥8)"


def _bucket_time(t):
    if pd.isna(t): return None
    return "rápido (<2.5 s)" if t < 2.5 else "normal (2.5–3.5 s)" if t <= 3.5 else "largo (>3.5 s)"


def prep(pl: pd.DataFrame) -> pd.DataFrame:
    pl = pl.copy()
    pl["dist_bucket"] = pl.yardsToGo.map(_bucket_dist)
    pl["time_bucket"] = pl.t_evento.map(_bucket_time)
    pl["gpos"] = range(len(pl))  # orden cronológico del jugador
    return pl


def mismatches(a: pd.Series, b: pd.Series) -> list[dict]:
    out = []
    for f, label, w in FACTORS:
        va, vb = a[f], b[f]
        if pd.isna(va) or pd.isna(vb):
            out.append({"factor": label, "peso": w, "referencia": None if pd.isna(va) else va, "seleccionada": None if pd.isna(vb) else vb, "difiere": False, "sin_dato": True})
        else:
            out.append({"factor": label, "peso": w, "referencia": va, "seleccionada": vb, "difiere": bool(va != vb), "sin_dato": False})
    return out


def quality(mm: list[dict]) -> dict:
    n = sum(1 for m in mm if m["difiere"])
    w = sum(m["peso"] for m in mm if m["difiere"])
    key = [m.get("factor") for m in mm if m["difiere"] and m["peso"] >= 2]
    level = "alta" if w <= 1 else "media" if w <= 3 else "baja"
    return {"nivel": level, "n_diferencias": n, "peso_diferencias": w, "diferencias_clave": key,
            "regla": "Alta: peso de diferencias ≤1 · Media: 2–3 · Baja: ≥4 (peso 2: alineación exacta, bloqueadores; peso 1: resto). No es una probabilidad."}


def pick_reference(pl: pd.DataFrame, sel_game: int, sel_play: int, mode: str):
    """Devuelve (fila_referencia | None, diferencias, calidad, info)."""
    pl = prep(pl)
    s = pl[(pl.gameId == sel_game) & (pl.playId == sel_play)]
    if s.empty:
        return None, [], None, {"motivo": "Jugada no encontrada"}
    s = s.iloc[0]
    pool = pl[pl.comparable & (pl.group == s.group) & (pl.gpos != s.gpos)]
    if mode == "live":
        pool = pool[pool.gpos < s.gpos]  # sin información futura
    if pool.empty:
        return None, [], None, {"motivo": "Sin jugadas previas comparables del mismo grupo de alineación" if mode == "live" else "Sin jugadas comparables del mismo grupo de alineación", "n_candidatas": 0}
    scores = []
    for _, r in pool.iterrows():
        mm = mismatches(r, s)
        scores.append((sum(m["peso"] for m in mm if m["difiere"]), int(r.gameId == s.gameId), abs(int(r.gpos) - int(s.gpos)), int(r.gameId), int(r.playId), r.gpos))
    best = min(scores)
    r = pool[pool.gpos == best[-1]].iloc[0]
    mm = mismatches(r, s)
    q = quality(mm)
    info = {"n_candidatas": int(len(pool)), "criterio": "Menor puntaje de diferencias de contexto; empate: otro partido (historial) y luego cercanía cronológica. No se usa la rapidez.",
            "solo_pasado": mode == "live", "mismo_partido": bool(r.gameId == s.gameId)}
    if q["nivel"] == "baja":
        info["aviso"] = "No hay una referencia suficientemente comparable: se muestra la mejor disponible, con diferencias marcadas. Interprétala con cautela."
    return r, mm, q, info
