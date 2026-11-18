"""Series por jugador-partido, reglas de revisión deterministas y explicación."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG
from .metrics import reference

STATUS_OK = "dentro_variacion"
STATUS_FLAG = "caida_para_revisar"
STATUS_INS = "evidencia_insuficiente"
STATUS_LABEL = {STATUS_OK: "Dentro de su variación habitual", STATUS_FLAG: "Caída observada para revisar",
                STATUS_INS: "Evidencia insuficiente"}


def _threshold(habit_pct, cfg=CFG) -> float:
    h = habit_pct if habit_pct == habit_pct and habit_pct is not None else 0.0
    return max(cfg.drop_pct, cfg.habit_mult * h)


def point_status(idx_list: list, ref: dict | None, cfg=CFG) -> str:
    """idx_list: índices comparables del partido hasta (e incluyendo) este punto."""
    if ref is None or not ref["ok"] or len(idx_list) < cfg.min_game_obs:
        return STATUS_INS
    T = _threshold(ref["habit_pct"], cfg)
    last = idx_list[-cfg.persistence:]
    return STATUS_FLAG if len(last) == cfg.persistence and all(v < 100 - T for v in last) else STATUS_OK


def smooth(vals: list, mode: str, cfg=CFG):
    """Tendencia suavizada. live: ventana final (solo pasado). retro: ventana centrada."""
    n = len(vals)
    out = []
    w = cfg.smooth_window
    for i in range(n):
        if mode == "live":
            seg = vals[max(0, i - w + 1): i + 1]
        else:
            h = w // 2
            seg = vals[max(0, i - h): i + h + 1]
        seg = [v for v in seg if v is not None]
        if len(seg) < 2:
            out.append((None, None, None)); continue
        m = float(np.mean(seg)); se = float(np.std(seg, ddof=1) / np.sqrt(len(seg)))
        out.append((m, m - 1.96 * se, m + 1.96 * se))
    return out


def _ctx(r) -> dict:
    return {"cuarto": int(r.quarter), "reloj": r.gameClock, "down": None if pd.isna(r.down) else int(r.down),
            "yardas_por_ganar": None if pd.isna(r.yardsToGo) else int(r.yardsToGo),
            "alineacion": r.pff_positionLinedUp, "grupo_alineacion": r.group,
            "formacion_ofensiva": r.offenseFormation, "cobertura": r.pff_passCoverage,
            "play_action": bool(r.pff_playAction == 1) if not pd.isna(r.pff_playAction) else None,
            "n_rushers": int(r.n_rushers), "bloqueadores_asignados": int(r.blockers),
            "t_evento_s": None if pd.isna(r.t_evento) else float(r.t_evento),
            "resultado": r.passResult, "personal_def": r.personnelD}


def player_game_series(df: pd.DataFrame, nfl_id: int, game_id: int, mode: str, cfg=CFG) -> dict:
    """df: tabla de intervenciones. mode: 'retro' (toda la evidencia) | 'live' (solo pasado)."""
    pl = df[df.nflId == nfl_id].reset_index(drop=True)
    pg = pl[pl.gameId == game_id]
    if pg.empty:
        return {"points": [], "gaps": [], "summary": None}
    refs_cache, pts, idx_hist = {}, [], []
    for pos, r in pg.iterrows():
        if mode == "retro":
            key = r.group
            if key not in refs_cache:
                refs_cache[key] = reference(pl, key, cfg)
            ref = refs_cache[key]
        else:
            ref = reference(pl.iloc[:pos], r.group, cfg)  # estrictamente jugadas anteriores
        idx = None
        if r.valid and ref["ok"]:
            idx = float(100 * r.v / ref["v_ref"])
        if r.comparable and idx is not None:
            idx_hist.append(idx)
        status = point_status(idx_hist, ref, cfg)
        pts.append({"playId": int(r.playId), "order": len(pts) + 1, "elapsed": r.elapsed,
                    "v": float(r.v) if r.valid else None, "disp": float(r.disp) if r.valid else None,
                    "index": idx, "comparable": bool(r.comparable), "valid": bool(r.valid),
                    "excl_reason": r.excl_reason or ("play action: contexto no comparable" if r.valid and not r.comparable else ""),
                    "status": status, "v_ref": ref["v_ref"], "ref_n": ref["n"], "ref_games": ref["games"],
                    "ref_basis": ref["basis"], "habit_pct": ref["habit_pct"], "ctx": _ctx(r)})
    # tendencia sobre puntos comparables con índice
    cmp_i = [i for i, p in enumerate(pts) if p["comparable"] and p["index"] is not None]
    sm = smooth([pts[i]["index"] for i in cmp_i], mode, cfg)
    for p in pts:
        p["trend"] = p["lo"] = p["hi"] = None
    for i, (m, lo, hi) in zip(cmp_i, sm):
        pts[i]["trend"], pts[i]["lo"], pts[i]["hi"] = m, lo, hi
    last = pts[-1]
    flagged = [p for p in pts if p["status"] == STATUS_FLAG]
    summary = {
        "mode": mode, "n_obs": len(pts), "n_valid": sum(p["valid"] for p in pts),
        "n_comparable": len(cmp_i), "n_with_index": len(cmp_i),
        "median_index": float(np.median([pts[i]["index"] for i in cmp_i])) if cmp_i else None,
        "status": last["status"], "status_label": STATUS_LABEL[last["status"]],
        "first_flag_playId": flagged[0]["playId"] if flagged else None,
        "n_flagged_points": len(flagged), "v_ref": last["v_ref"], "ref_n": last["ref_n"],
        "ref_games": last["ref_games"], "ref_basis": last["ref_basis"], "habit_pct": last["habit_pct"],
        "threshold_pts": _threshold(last["habit_pct"], cfg), "games_with_data": int(pl.gameId.nunique()),
        "player_total_obs": int(len(pl)),
    }
    return {"points": pts, "gaps": observation_gaps(pg, game_id, df, cfg), "summary": summary}


def observation_gaps(pg: pd.DataFrame, game_id: int, df: pd.DataFrame, cfg=CFG) -> list:
    """Intervalos sin observación como Pass Rush. NO equivalen a descanso confirmado."""
    team = pg.defensiveTeam.iloc[0]
    tp = df[(df.gameId == game_id) & (df.defensiveTeam == team)].drop_duplicates("playId").sort_values("elapsed")
    seen = set(pg.playId)
    order = list(tp.playId)
    el = dict(zip(tp.playId, tp.elapsed))
    gaps, run = [], []
    for pid in order + [None]:
        if pid is not None and pid not in seen:
            run.append(pid); continue
        if len(run) >= cfg.gap_plays:
            end = el.get(pid, el[run[-1]]) if pid is not None else el[run[-1]]
            gaps.append({"start": el[run[0]], "end": end, "n_plays": len(run), "label": "Sin observación como Pass Rush (no confirma descanso)"})
        run = []
    return gaps


def review_card(series: dict, mode: str, cfg=CFG) -> dict:
    """Tarjeta 'Qué revisaría el entrenador' (texto determinista a partir de los datos)."""
    pts, s = series["points"], series["summary"]
    if not pts or s is None:
        return {"status": STATUS_INS, "status_label": STATUS_LABEL[STATUS_INS], "cambio": "Sin observaciones.", "items": []}
    cmp_pts = [p for p in pts if p["comparable"] and p["index"] is not None]
    st = s["status"]
    last = cmp_pts[-cfg.persistence:] if cmp_pts else []
    out = {"status": st, "status_label": STATUS_LABEL[st], "mode": mode,
           "mode_label": "Retrospectivo (toda la evidencia disponible)" if mode == "retro" else "En ese momento (solo datos hasta esa intervención)",
           "rotation_note": "Participación y descanso NO verificados: no se emite sugerencia de rotación; solo revisión de la secuencia.",
           "exposure_verified": False}
    if st == STATUS_INS:
        why = []
        if s["ref_n"] < cfg.min_ref_n: why.append(f"referencia con {s['ref_n']} intervenciones (mínimo {cfg.min_ref_n})")
        if s["ref_games"] < cfg.min_ref_games: why.append(f"referencia con {s['ref_games']} partido(s) (mínimo {cfg.min_ref_games})")
        if s["n_comparable"] < cfg.min_game_obs: why.append(f"{s['n_comparable']} intervenciones comparables en el partido (mínimo {cfg.min_game_obs})")
        out.update(cambio="No hay evidencia suficiente para evaluar un cambio.", referencia="; ".join(why) or "Referencia no válida.", sustento=_sust(s), alternativas=[], revisar=["Usar solo el comparador de replays como exploración; no concluir."])
        return out
    vs = np.mean([p["v"] for p in last]); idxm = np.mean([p["index"] for p in last])
    out["cambio"] = (f"Rapidez media 0–1 s tras el snap en las últimas {len(last)} intervenciones comparables: {vs:.2f} yd/s "
                     f"(índice medio {idxm:.0f}, donde 100 = su propia referencia).")
    out["referencia"] = (f"Mediana propia {s['v_ref']:.2f} yd/s sobre {s['ref_n']} intervenciones en {s['ref_games']} partido(s); {s['ref_basis']}. "
                         f"Variación habitual ≈ {s['habit_pct']:.0f}%; umbral para revisar: {s['threshold_pts']:.0f} puntos bajo 100 "
                         f"en {cfg.persistence} intervenciones consecutivas (heurístico configurable, no médico).")
    out["sustento"] = _sust(s)
    alts = []
    if last:
        pr = np.mean([p["ctx"]["n_rushers"] for p in last]); allr = np.mean([p["ctx"]["n_rushers"] for p in cmp_pts])
        bl = np.mean([p["ctx"]["bloqueadores_asignados"] for p in last]); allbl = np.mean([p["ctx"]["bloqueadores_asignados"] for p in cmp_pts])
        te = [p["ctx"]["t_evento_s"] for p in last if p["ctx"]["t_evento_s"] is not None]
        alts.append(f"Bloqueadores asignados: {bl:.1f} en esas jugadas vs {allbl:.1f} promedio del partido (más contacto reduce la salida sin implicar cansancio).")
        alts.append(f"Rushers por jugada: {pr:.1f} vs {allr:.1f}; stunts/contención/cobertura pueden reducir la rapidez inicial.")
        if te: alts.append(f"Tiempo hasta lanzamiento/sack: {np.mean(te):.1f} s en esas jugadas (liberación rápida limita la ventana).")
        alts.append("Alineaciones: " + ", ".join(sorted({p["ctx"]["alineacion"] for p in last})) + "; coberturas: " + ", ".join(sorted({str(p["ctx"]["cobertura"]) for p in last})) + ".")
    alts.append("Tamaño de muestra pequeño dentro del partido y ruido del tracking (10 fps).")
    out["alternativas"] = alts
    rev = ["Ver el video de las jugadas marcadas junto a una jugada de referencia con contexto similar.",
           "Comprobar asignación (stunt, contención, spy) y si hubo doble bloqueo antes de atribuirlo a explosividad."]
    if st == STATUS_FLAG:
        rev.insert(0, "Revisar esta secuencia: la salida observada es consistentemente menor a su referencia propia.")
    else:
        rev.insert(0, "Sin caída persistente respecto a su referencia; no hay motivo de revisión por este indicador.")
    out["revisar"] = rev
    return out


def _sust(s):
    return f"{s['n_comparable']} intervenciones comparables en este partido; referencia: {s['ref_n']} intervenciones / {s['ref_games']} partidos."
