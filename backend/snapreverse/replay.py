"""Replays de tracking y comparación de dos intervenciones sincronizadas al snap."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG, SNAP_EVENTS
from .data_access import Tables

FIELD_W = 53.3


def build_replay(tb: Tables, game_id: int, play_id: int, nfl_id: int) -> dict | None:
    trk = tb.tracking(game_id)
    t = trk[trk.playId == play_id]
    if t.empty:
        return None
    t = t.sort_values(["frameId", "nflId"])
    flip = (t.playDirection.iloc[0] == "left")  # normaliza: ataque siempre hacia la derecha
    x = 120 - t.x if flip else t.x
    y = FIELD_W - t.y if flip else t.y
    t = t.assign(xn=x, yn=y)
    ev = t[t.event.isin(SNAP_EVENTS)]
    if ev.empty:
        snap = None
    else:
        e = ev.assign(p=(ev.event != "ball_snap").astype(int)).sort_values(["p", "frameId"])
        snap = int(e.frameId.iloc[0])
    frames = sorted(int(f) for f in t.frameId.unique())
    events = {}
    for f, e in t[t.event != "None"].groupby("frameId").event.first().items():
        events[int(f)] = str(e)
    pff = tb.pff[(tb.pff.gameId == game_id) & (tb.pff.playId == play_id)].set_index("nflId")
    names = tb.players.set_index("nflId")
    tracks, meta = {}, []
    for pid, g in t.groupby(t.nflId.fillna(-1)):
        g = g.set_index("frameId").reindex(frames)
        key = "ball" if pid == -1 else str(int(pid))
        tracks[key] = [[None if np.isnan(a) else round(float(a), 2), None if np.isnan(b) else round(float(b), 2),
                        None if np.isnan(c) else round(float(c), 2)] for a, b, c in zip(g.xn, g.yn, g.s)]
        if pid != -1:
            r = pff.loc[int(pid)] if int(pid) in pff.index else None
            meta.append({"nflId": int(pid), "team": g.team.dropna().iloc[0] if g.team.notna().any() else None,
                         "jersey": None if g.jerseyNumber.isna().all() else int(g.jerseyNumber.dropna().iloc[0]),
                         "name": names.displayName.get(int(pid)), "pos": names.officialPosition.get(int(pid)),
                         "role": None if r is None else r.pff_role, "lined_up": None if r is None else r.pff_positionLinedUp,
                         "target": int(pid) == int(nfl_id)})
    play = tb.plays[(tb.plays.gameId == game_id) & (tb.plays.playId == play_id)].iloc[0]
    ball = tracks.get("ball")
    los = None
    if snap is not None and ball is not None:
        i = frames.index(snap)
        los = ball[i][0]
    return {"gameId": game_id, "playId": play_id, "frames": frames, "snap_frame": snap,
            "window": None if snap is None else [snap + 1, snap + CFG.window_frames],
            "events": events, "tracks": tracks, "players": meta, "los_x": los, "fps": CFG.fps,
            "description": play.playDescription, "defensive_team": play.defensiveTeam,
            "possession_team": play.possessionTeam, "direction_normalized": "ataque hacia la derecha",
            "sync_note": "Sincronizado en ball_snap (evento común). La interpolación es solo visual." if snap is not None
            else "Sin snap en esta jugada: no se sincroniza."}


CONTEXT_FIELDS = [("cuarto", "Cuarto"), ("reloj", "Reloj"), ("down", "Down"), ("yardas_por_ganar", "Yardas por ganar"),
                  ("alineacion", "Alineación"), ("formacion_ofensiva", "Formación ofensiva"), ("cobertura", "Cobertura"), ("tipo_cobertura", "Tipo de cobertura"),
                  ("play_action", "Play action"), ("n_rushers", "Rushers"), ("bloqueadores_asignados", "Bloqueadores asignados"),
                  ("t_evento_s", "Tiempo hasta lanzamiento/sack (s)"), ("personal_def", "Personal defensivo"), ("resultado", "Resultado")]


def context_diff(a: dict, b: dict) -> list:
    out = []
    for k, label in CONTEXT_FIELDS:
        va, vb = a.get(k), b.get(k)
        out.append({"campo": label, "referencia": va, "seleccionada": vb, "difiere": va != vb})
    return out


def default_reference(pl: pd.DataFrame, sel: pd.Series, v_ref: float | None, exclude_play: int):
    """Jugada de referencia: comparable, mismo grupo de alineación, rapidez más cercana a la mediana propia.
    Criterio fijo (no elegido para exagerar caídas); desempate por misma formación ofensiva y menor |Δ|."""
    c = pl[pl.comparable & (pl.group == sel.group) & ~((pl.gameId == sel.gameId) & (pl.playId == exclude_play))]
    if c.empty or v_ref is None:
        return None
    c = c.assign(d=(c.v - v_ref).abs(), same_form=(c.offenseFormation != sel.offenseFormation).astype(int))
    return c.sort_values(["d", "same_form"]).iloc[0]
