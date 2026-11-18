"""Cálculo de SnapReverse — Índice de Explosividad Relativa.

v = rapidez media (yd/s, columna `s` del tracking) en la ventana (snap, snap+1.0 s], 10 muestras originales.
Índice = 100 * v / v_ref, v_ref = mediana de v del mismo defensivo (rol Pass Rush) en su referencia.
100 = su propia referencia. NO es energía, fatiga ni capacidad fisiológica.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG, ALIGN_GROUP, DEFAULT_GROUP, SNAP_EVENTS, TERMINAL_EVENTS
from .data_access import Tables, clock_to_elapsed

LOAD_COLS = ["gameId", "playId", "nflId", "frameId", "x", "y", "s", "event"]


def snap_frames(trk: pd.DataFrame) -> pd.Series:
    """Frame del snap por jugada (prefiere ball_snap sobre autoevent_ballsnap)."""
    e = trk[trk.event.isin(SNAP_EVENTS)][["playId", "frameId", "event"]].drop_duplicates()
    e["pri"] = (e.event != "ball_snap").astype(int)
    e = e.sort_values(["playId", "pri", "frameId"]).drop_duplicates("playId")
    return e.set_index("playId").frameId


def game_interventions(trk: pd.DataFrame, pr_rows: pd.DataFrame, cfg=CFG) -> pd.DataFrame:
    """Una fila por (jugada, defensivo Pass Rush) con la métrica cruda y banderas de calidad.

    Solo usa muestras originales posteriores al snap, hasta snap+window.
    """
    snap = snap_frames(trk).rename("snap")
    W = cfg.window_frames
    if snap.empty:  # sin snap no se calcula nada "desde el snap"
        return pd.DataFrame(columns=["playId", "nflId", "v", "n_frames", "disp", "valid", "snap_frame"])
    keys = pr_rows[["playId", "nflId"]].drop_duplicates()
    t = trk[trk.nflId.isin(keys.nflId.unique()) & trk.playId.isin(snap.index)]
    t = t.merge(keys, on=["playId", "nflId"], how="inner")  # solo pares (jugada, jugador) con rol Pass Rush
    t = t.merge(snap, left_on="playId", right_index=True)
    t["rel"] = t.frameId - t.snap
    t = t[(t.rel >= 0) & (t.rel <= W)]
    # Un jugador-por-jugada: validar unicidad de frames
    if t.duplicated(["playId", "nflId", "rel"]).any():
        raise ValueError("frames duplicados en tracking")
    post = t[t.rel >= 1]
    agg = post.groupby(["playId", "nflId"]).agg(v=("s", "mean"), n_frames=("s", "count"),
                                                 s_nan=("s", lambda x: x.isna().sum())).reset_index()
    p0 = t[t.rel == 0][["playId", "nflId", "x", "y"]].rename(columns={"x": "x0", "y": "y0"})
    pW = t[t.rel == W][["playId", "nflId", "x", "y"]].rename(columns={"x": "x1", "y": "y1"})
    out = agg.merge(p0, on=["playId", "nflId"], how="left").merge(pW, on=["playId", "nflId"], how="left")
    out["disp"] = np.hypot(out.x1 - out.x0, out.y1 - out.y0)
    # eventos terminales dentro de la ventana (jugada terminó antes de 1 s)
    ev = trk[trk.playId.isin(snap.index) & trk.event.isin(TERMINAL_EVENTS)]
    ev = ev[(ev.frameId - ev.playId.map(snap)) <= W]
    out["terminal_en_ventana"] = out.playId.isin(ev.playId.unique())
    # tiempo hasta lanzamiento / fin (contexto)
    ttt = trk[trk.event.isin(["pass_forward", "autoevent_passforward", "qb_sack", "qb_strip_sack"])]
    ttt = ttt.assign(t_evt=(ttt.frameId - ttt.playId.map(snap)) / cfg.fps)
    ttt = ttt.groupby(ttt.playId.values).t_evt.min()
    out["t_evento"] = out.playId.map(ttt)
    out["snap_frame"] = out.playId.map(snap)
    out["valid"] = (out.n_frames == W) & (out.s_nan == 0) & out.x0.notna() & out.disp.notna() & ~out.terminal_en_ventana
    out["excl_reason"] = np.select(
        [out.n_frames < W, out.s_nan > 0, out.terminal_en_ventana], ["ventana incompleta", "rapidez faltante", "jugada terminó <1 s"], "")
    # jugadas sin snap: no se calculan (se reportan aparte)
    return out


def build_interventions(tb: Tables, cfg=CFG) -> pd.DataFrame:
    """Tabla completa de intervenciones observadas (Pass Rush) de todos los partidos."""
    pff, plays, games = tb.pff, tb.plays, tb.games
    pr = pff[pff.pff_role == "Pass Rush"][["gameId", "playId", "nflId", "pff_positionLinedUp"]].copy()
    nrush = pr.groupby(["gameId", "playId"]).size().rename("n_rushers").reset_index()
    blk = pff[pff.pff_nflIdBlockedPlayer.notna()].groupby(["gameId", "playId", "pff_nflIdBlockedPlayer"]).size()
    blk = blk.rename("blockers").reset_index().rename(columns={"pff_nflIdBlockedPlayer": "nflId"})
    blk["nflId"] = blk.nflId.astype(int)
    parts, no_snap = [], 0
    for gid in sorted(pr.gameId.unique()):
        try:
            trk = tb.tracking(gid, cols=LOAD_COLS, cache=False)
        except Exception:
            continue
        g = game_interventions(trk, pr[pr.gameId == gid])
        g["gameId"] = gid
        parts.append(g)
    df = pd.concat(parts, ignore_index=True)
    n0 = len(df)
    df = df.merge(pr, on=["gameId", "playId", "nflId"], how="inner", validate="1:1")
    df = df.merge(nrush, on=["gameId", "playId"], how="left", validate="m:1")
    df = df.merge(blk, on=["gameId", "playId", "nflId"], how="left", validate="1:1")
    df["blockers"] = df.blockers.fillna(0).astype(int)
    pcols = ["gameId", "playId", "quarter", "down", "yardsToGo", "gameClock", "defensiveTeam", "possessionTeam",
             "offenseFormation", "personnelD", "defendersInBox", "dropBackType", "pff_playAction",
             "pff_passCoverage", "passResult", "playDescription"]
    df = df.merge(plays[pcols], on=["gameId", "playId"], how="left", validate="m:1")
    gcols = games[["gameId", "week", "gameDate", "gameTimeEastern", "homeTeamAbbr", "visitorTeamAbbr"]]
    df = df.merge(gcols, on="gameId", how="left", validate="m:1")
    assert len(df) == n0, "multiplicación de filas en uniones"
    df["comparable"] = df.valid & (df.pff_playAction.fillna(0) == 0)  # play action cambia la salida: contexto no comparable
    df["group"] = df.pff_positionLinedUp.map(ALIGN_GROUP).fillna(DEFAULT_GROUP)
    df["elapsed"] = [clock_to_elapsed(q, c) for q, c in zip(df.quarter, df.gameClock)]
    df["gdt"] = pd.to_datetime(df.gameDate + " " + df.gameTimeEastern, format="%m/%d/%Y %H:%M:%S")
    df = df.sort_values(["nflId", "gdt", "gameId", "elapsed", "playId"]).reset_index(drop=True)
    df["opponent"] = np.where(df.defensiveTeam == df.homeTeamAbbr, df.visitorTeamAbbr, df.homeTeamAbbr)
    return df


def robust_habit(v: np.ndarray) -> float:
    """Variación habitual relativa (%): 1.4826*MAD / mediana * 100."""
    v = v[~np.isnan(v)]
    if len(v) < 3:
        return float("nan")
    med = np.median(v)
    if med < CFG.min_ref_speed:
        return float("nan")
    return float(1.4826 * np.median(np.abs(v - med)) / med * 100)


def reference(prev: pd.DataFrame, group: str, cfg=CFG) -> dict:
    """Referencia propia a partir de intervenciones válidas `prev` (el llamador decide qué incluye)."""
    prev = prev[prev.comparable]
    n_all, g_all = len(prev), prev.gameId.nunique()
    sub = prev[prev.group == group]
    if len(sub) >= cfg.group_ref_min_n and sub.gameId.nunique() >= 2:
        use, basis = sub, f"mismo grupo de alineación ({group})"
    else:
        use, basis = prev, "todas sus intervenciones (grupo de alineación con pocas muestras)"
    ref = float(np.median(use.v)) if len(use) else float("nan")
    ok = (len(use) >= cfg.min_ref_n and use.gameId.nunique() >= cfg.min_ref_games and ref >= cfg.min_ref_speed)
    return {"v_ref": ref if ref == ref else None, "n": int(len(use)), "games": int(use.gameId.nunique()),
            "basis": basis, "habit_pct": robust_habit(use.v.values) if len(use) else float("nan"),
            "ok": bool(ok), "n_all": int(n_all), "games_all": int(g_all)}
