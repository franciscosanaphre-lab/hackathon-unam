"""Herramientas deterministas (solo lectura) que Nova puede invocar. Lista cerrada, parámetros validados.
Cada resultado incluye `evidence`: tarjetas construidas por Python (no por el LLM)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import CFG
from ..data_access import clean
from ..replay import build_replay, CONTEXT_FIELDS
from ..review import STATUS_LABEL, player_game_series


class ToolError(Exception):
    pass


class Ctx:
    """Contexto fijado por el backend: el LLM no puede salirse de este jugador/partido."""

    def __init__(self, svc, nfl_id: int, game_id: int, mode: str):
        self.svc, self.nfl_id, self.game_id, self.mode = svc, nfl_id, game_id, mode
        self.evidence: list[dict] = []
        self.known_plays: set[int] = set()
        self.numbers: list[float] = [float(nfl_id), float(game_id)]
        self._series = None

    def series(self, nfl_id=None, game_id=None, mode=None):
        nid, gid, m = nfl_id or self.nfl_id, game_id or self.game_id, mode or self.mode
        s = player_game_series(self.svc.df, nid, gid, m)
        if not s["points"]:
            raise ToolError("Sin intervenciones de ese jugador en ese partido")
        names = self.svc.tb.players.set_index("nflId")
        g = self.svc.tb.games[self.svc.tb.games.gameId == gid].iloc[0]
        s["player"] = {"nflId": nid, "name": names.displayName.get(nid), "pos": names.officialPosition.get(nid)}
        s["game"] = {"gameId": gid, "week": int(g.week), "home": g.homeTeamAbbr, "away": g.visitorTeamAbbr}
        return s

    def add_ev(self, kind: str, title: str, data: dict, play_id: int | None = None, game_id: int | None = None) -> str:
        eid = f"E{len(self.evidence) + 1}"
        self.evidence.append({"id": eid, "type": kind, "title": title, "playId": play_id, "gameId": game_id or self.game_id, "data": clean(data)})
        if play_id is not None:
            self.known_plays.add(int(play_id))
        self._collect(data)
        return eid

    def _collect(self, o):
        if isinstance(o, dict):
            for v in o.values(): self._collect(v)
        elif isinstance(o, (list, tuple)):
            for v in o: self._collect(v)
        elif isinstance(o, (int, float, np.integer, np.floating)) and not isinstance(o, bool) and np.isfinite(o):
            self.numbers.append(float(o))


def _check_scope(ctx: Ctx, player_id, game_id):
    if int(player_id) != ctx.nfl_id or int(game_id) != ctx.game_id:
        raise ToolError("Solo se permite consultar el jugador y partido del contexto actual.")


def _med(a): return float(np.median(a)) if len(a) else None


def _quality(s: dict) -> dict:
    sm = s["summary"]
    ok = sm["ref_n"] >= CFG.min_ref_n and sm["ref_games"] >= CFG.min_ref_games and sm["n_comparable"] >= CFG.min_game_obs
    return {"suficiente": bool(ok), "n_obs": sm["n_obs"], "n_comparable": sm["n_comparable"], "ref_n": sm["ref_n"], "ref_games": sm["ref_games"],
            "criterio": f"referencia ≥{CFG.min_ref_n} intervenciones y ≥{CFG.min_ref_games} partidos; ≥{CFG.min_game_obs} comparables en el partido"}


def get_player_performance(ctx: Ctx, player_id: int, game_id: int) -> dict:
    _check_scope(ctx, player_id, game_id)
    s = ctx.series()
    sm = s["summary"]
    idx = [p["index"] for p in s["points"] if p["comparable"] and p["index"] is not None]
    vs = [p["v"] for p in s["points"] if p["comparable"] and p["v"] is not None]
    out = {"jugador": s["player"]["name"], "posicion": s["player"]["pos"], "partido": f"{s['game']['away']} @ {s['game']['home']} (semana {s['game']['week']})", "modo": ctx.mode,
           "estado": sm["status_label"], "indice_mediano": sm["median_index"], "referencia_yd_s": sm["v_ref"],
           "variacion_habitual_pct": sm["habit_pct"], "umbral_puntos": sm["threshold_pts"],
           "n_observadas": sm["n_obs"], "n_comparables": sm["n_comparable"], "ref_n": sm["ref_n"], "ref_partidos": sm["ref_games"],
           "puntos_con_marca": sm["n_flagged_points"],
           "rapidez_media_yd_s": float(np.mean(vs)) if vs else None, "desv_indice": float(np.std(idx, ddof=1)) if len(idx) > 1 else None,
           "indice_mediano_ultimas_5_intervenciones": _med(idx[-5:]), "calidad": _quality(s),
           "limitaciones": ["Participación y descanso no verificados.", "Solo jugadas de pase con rol Pass Rush.", "Rapidez baja puede deberse a contención, stunt, cobertura o contacto."]}
    eid = ctx.add_ev("resumen", "Resumen de métricas del partido", {k: out[k] for k in ("indice_mediano", "referencia_yd_s", "variacion_habitual_pct", "n_comparables", "ref_n", "ref_partidos", "puntos_con_marca")})
    out["evidence_id"] = eid
    return out


def _boot_diff(a: np.ndarray, b: np.ndarray, n=1000, seed=7):
    rng = np.random.default_rng(seed)
    d = [np.median(rng.choice(b, len(b))) - np.median(rng.choice(a, len(a))) for _ in range(n)]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def investigate_performance_change(ctx: Ctx, player_id: int, game_id: int) -> dict:
    _check_scope(ctx, player_id, game_id)
    modes = {}
    for m in ("live", "retro"):
        s = ctx.series(mode=m)
        sm = s["summary"]
        modes[m] = {"estado_final": sm["status_label"], "puntos_con_marca": sm["n_flagged_points"], "primera_marca_playId": sm["first_flag_playId"],
                    "ref_n": sm["ref_n"], "ref_partidos": sm["ref_games"]}
    s = ctx.series()
    pts = [p for p in s["points"] if p["comparable"] and p["index"] is not None]
    out = {"modo_principal": ctx.mode, "por_modo": modes, "calidad": _quality(s)}
    if len(pts) >= 2 * CFG.persistence:
        h = len(pts) // 2
        a, b = np.array([p["index"] for p in pts[:h]]), np.array([p["index"] for p in pts[h:]])
        lo, hi = _boot_diff(a, b)
        out["primera_mitad_mediana"], out["segunda_mitad_mediana"] = _med(a), _med(b)
        out["cambio_mediana_puntos"] = _med(b) - _med(a)
        out["intervalo_bootstrap_95"] = [lo, hi]
        out["n_mitades"] = [len(a), len(b)]
    sm = s["summary"]
    flagged_both = modes["live"]["puntos_con_marca"] > 0 and modes["retro"]["puntos_con_marca"] > 0
    if not out["calidad"]["suficiente"]:
        v, expl = "evidencia_insuficiente", "No hay muestra o referencia suficiente para evaluar un cambio."
    elif flagged_both:
        v, expl = "caida_persistente_en_ambos_modos", "Hay marca de caída persistente tanto en modo en-ese-momento como retrospectivo."
    elif sm["n_flagged_points"] > 0 or modes["live"]["puntos_con_marca"] + modes["retro"]["puntos_con_marca"] > 0:
        v, expl = "marca_no_robusta", "Hay marca en un solo modo: la caída no se sostiene al cambiar la referencia; tratar con cautela."
    else:
        v, expl = "estable", "No hay caída persistente respecto a su referencia propia."
    out["veredicto"], out["explicacion"] = v, expl
    out["intervalo_incluye_cero"] = bool(out.get("intervalo_bootstrap_95") and out["intervalo_bootstrap_95"][0] <= 0 <= out["intervalo_bootstrap_95"][1])
    out["nota"] = "Caída observada ≠ fatiga. No se evalúa participación ni descanso."
    eid = ctx.add_ev("cambio", "Investigación de cambio de rendimiento", {k: out[k] for k in out if k in ("veredicto", "primera_mitad_mediana", "segunda_mitad_mediana", "cambio_mediana_puntos", "intervalo_bootstrap_95", "n_mitades")} | {"marcas_live": modes["live"]["puntos_con_marca"], "marcas_retro": modes["retro"]["puntos_con_marca"]})
    out["evidence_id"] = eid
    return out


CRITERIA = ("lowest_index", "highest_index", "first_flag", "reference_like", "contrasting_context")


def find_relevant_plays(ctx: Ctx, player_id: int, game_id: int, criteria: str, limit: int = 3) -> dict:
    _check_scope(ctx, player_id, game_id)
    if criteria not in CRITERIA:
        raise ToolError(f"criteria debe ser uno de {CRITERIA}")
    limit = max(1, min(int(limit), 5))
    s = ctx.series()
    pts = [p for p in s["points"] if p["comparable"] and p["index"] is not None]
    if not pts:
        return {"jugadas": [], "nota": "Sin intervenciones comparables con índice."}
    if criteria == "lowest_index": sel, rule = sorted(pts, key=lambda p: p["index"])[:limit], "Menor índice del partido (puede ser un valor extremo/ruidoso)."
    elif criteria == "highest_index": sel, rule = sorted(pts, key=lambda p: -p["index"])[:limit], "Mayor índice del partido (contraste)."
    elif criteria == "first_flag":
        sel = [p for p in s["points"] if p["status"] == "caida_para_revisar"][:limit]
        rule = "Primeras jugadas con marca de caída persistente."
    elif criteria == "reference_like": sel, rule = sorted(pts, key=lambda p: abs(p["index"] - 100))[:limit], "Jugadas más cercanas a su referencia (índice≈100)."
    else:
        last = pts[-1]
        sel = sorted([p for p in pts if p["playId"] != last["playId"] and p["ctx"]["grupo_alineacion"] == last["ctx"]["grupo_alineacion"]], key=lambda p: -abs(p["index"] - last["index"]))[:limit]
        rule = "Jugadas del mismo grupo de alineación con mayor diferencia de índice respecto a la última."
    res = []
    for p in sel:
        row = {"playId": p["playId"], "orden": p["order"], "reloj": f"Q{p['ctx']['cuarto']} {p['ctx']['reloj']}", "indice": p["index"], "rapidez_yd_s": p["v"],
               "alineacion": p["ctx"]["alineacion"], "down": p["ctx"]["down"], "yardas": p["ctx"]["yardas_por_ganar"], "cobertura": p["ctx"]["cobertura"],
               "bloqueadores": p["ctx"]["bloqueadores_asignados"], "marca": p["status"] == "caida_para_revisar"}
        row["evidence_id"] = ctx.add_ev("jugada", f"Jugada {p['playId']} (índice {p['index']:.0f})", row, play_id=p["playId"])
        res.append(row)
    return {"criterio": criteria, "regla_de_seleccion": rule, "jugadas": res, "nota": "Selección por regla fija; no implica causalidad."}


def _accel(rep: dict | None, nfl_id: int):
    """Aceleración robusta: mediana de Δs/Δt (yd/s²) en la ventana 1–10 muestras posteriores al snap."""
    if not rep or rep["snap_frame"] is None:
        return None
    tr = rep["tracks"].get(str(nfl_id))
    if not tr:
        return None
    b = rep["frames"].index(rep["snap_frame"])
    sp = [tr[i][2] for i in range(b + 1, b + 11) if i < len(tr) and tr[i][2] is not None]
    if len(sp) < 5:
        return None
    return float(np.median(np.diff(sp)) * rep["fps"])


def compare_interventions(ctx: Ctx, game_id: int, play_id_1: int, play_id_2: int, ref_game_id: int | None = None) -> dict:
    """play_id_1 = referencia, play_id_2 = seleccionada (ambas del jugador del contexto)."""
    pl = ctx.svc.df[ctx.svc.df.nflId == ctx.nfl_id]
    def get(g, p):
        r = pl[(pl.gameId == g) & (pl.playId == p)]
        if r.empty:
            raise ToolError(f"La jugada {p} no es una intervención observada de este jugador en el partido {g}")
        return r.iloc[0]
    g1 = int(ref_game_id or game_id)
    a, b = get(g1, int(play_id_1)), get(int(game_id), int(play_id_2))
    from ..replay import context_diff
    ra, rb = build_replay(ctx.svc.tb, g1, int(play_id_1), ctx.nfl_id), build_replay(ctx.svc.tb, int(game_id), int(play_id_2), ctx.nfl_id)
    ca = {"cuarto": int(a.quarter), "reloj": a.gameClock, "down": None if pd.isna(a.down) else int(a.down), "yardas_por_ganar": None if pd.isna(a.yardsToGo) else int(a.yardsToGo),
          "alineacion": a.pff_positionLinedUp, "formacion_ofensiva": a.offenseFormation, "cobertura": a.pff_passCoverage, "play_action": bool(a.pff_playAction == 1),
          "n_rushers": int(a.n_rushers), "bloqueadores_asignados": int(a.blockers), "t_evento_s": None if pd.isna(a.t_evento) else float(a.t_evento), "personal_def": a.personnelD, "resultado": a.passResult}
    cb = {"cuarto": int(b.quarter), "reloj": b.gameClock, "down": None if pd.isna(b.down) else int(b.down), "yardas_por_ganar": None if pd.isna(b.yardsToGo) else int(b.yardsToGo),
          "alineacion": b.pff_positionLinedUp, "formacion_ofensiva": b.offenseFormation, "cobertura": b.pff_passCoverage, "play_action": bool(b.pff_playAction == 1),
          "n_rushers": int(b.n_rushers), "bloqueadores_asignados": int(b.blockers), "t_evento_s": None if pd.isna(b.t_evento) else float(b.t_evento), "personal_def": b.personnelD, "resultado": b.passResult}
    diffs = [d for d in context_diff(ca, cb) if d["difiere"]]
    ref = ctx.series()["summary"]["v_ref"]
    aa, ab = _accel(ra, ctx.nfl_id), _accel(rb, ctx.nfl_id)
    out = {"referencia": {"gameId": g1, "playId": int(play_id_1), "rapidez_yd_s": float(a.v), "desplazamiento_yd": float(a.disp), "aceleracion_mediana_yd_s2": aa, "comparable": bool(a.comparable)},
           "seleccionada": {"gameId": int(game_id), "playId": int(play_id_2), "rapidez_yd_s": float(b.v), "desplazamiento_yd": float(b.disp), "aceleracion_mediana_yd_s2": ab, "comparable": bool(b.comparable)},
           "diferencia_rapidez_yd_s": float(b.v - a.v), "diferencia_desplazamiento_yd": float(b.disp - a.disp),
           "diferencia_aceleracion_yd_s2": None if aa is None or ab is None else ab - aa,
           "indice_seleccionada_vs_ref_propia": None if not ref or ref < CFG.min_ref_speed else float(100 * b.v / ref),
           "diferencias_de_contexto": [{"campo": d["campo"], "referencia": d["referencia"], "seleccionada": d["seleccionada"]} for d in diffs],
           "sincronizacion": "ball_snap" if ra and rb and ra["snap_frame"] is not None and rb["snap_frame"] is not None else "sin snap común",
           "ventana": "10 muestras (1.0 s) posteriores al snap",
           "calidad": "ventana completa en ambas" if a.valid and b.valid else "ventana incompleta en alguna",
           "advertencias": (["Una es play action y la otra no."] if ca["play_action"] != cb["play_action"] else []) + (["Distinto grupo de alineación."] if a.group != b.group else []),
           "nota": "Diferencias calculadas; no se atribuyen a cansancio, habilidad ni errores técnicos."}
    eid = ctx.add_ev("comparacion", f"Comparación jugada {play_id_1} vs {play_id_2}", {k: out[k] for k in ("diferencia_rapidez_yd_s", "diferencia_desplazamiento_yd", "diferencia_aceleracion_yd_s2", "indice_seleccionada_vs_ref_propia")}, play_id=int(play_id_2))
    ctx.known_plays.add(int(play_id_1))
    out["evidence_id"] = eid
    return out


def evaluate_available_alternatives(ctx: Ctx, player_id: int, game_id: int) -> dict:
    """Alternativas realmente observadas (alineación del propio jugador y compañeros del mismo grupo). No ordena por 'mejor'."""
    _check_scope(ctx, player_id, game_id)
    df = ctx.svc.df
    pl = df[(df.nflId == ctx.nfl_id) & df.comparable]
    by_al = []
    for al, g in pl.groupby("pff_positionLinedUp"):
        if len(g) >= 3:
            by_al.append({"alineacion": al, "n": int(len(g)), "partidos": int(g.gameId.nunique()), "rapidez_mediana_yd_s": _med(g.v.values)})
    by_al.sort(key=lambda r: -r["n"])
    me = df[(df.nflId == ctx.nfl_id) & (df.gameId == ctx.game_id)].iloc[0]
    mates = df[(df.gameId == ctx.game_id) & (df.defensiveTeam == me.defensiveTeam) & (df.nflId != ctx.nfl_id) & df.comparable & (df.group == me.group)]
    names = ctx.svc.tb.players.set_index("nflId").displayName
    team = []
    for nid, g in mates.groupby("nflId"):
        if len(g) >= 4:
            sr = player_game_series(df, int(nid), ctx.game_id, "live")["summary"]
            team.append({"nombre": names.get(nid, str(nid)), "grupo": me.group, "n_en_partido": int(len(g)), "rapidez_mediana_yd_s": _med(g.v.values), "indice_mediano": sr["median_index"]})
    team.sort(key=lambda r: -r["n_en_partido"])
    out = {"alineaciones_observadas_del_jugador": by_al[:5], "companeros_mismo_grupo_en_partido": team[:4],
           "factores_de_confusion": ["Diferentes jugadas, rivales y bloqueos entre muestras.", "Muestras pequeñas por alineación/partido.", "Los índices de distintos jugadores son relativos a SU referencia: no son comparables como talento."],
           "limitaciones": ["El dataset no trae llamadas tácticas, asignaciones ni participación completa: no se puede afirmar qué alternativa es mejor.", "No se ordena por 'mejor'; solo se listan opciones observadas para revisión."],
           "opciones_para_revision": ["Comparar jugadas del mismo jugador desde su alineación habitual vs otra, si hay muestra.", "Revisar en video si compañeros del mismo grupo tuvieron contextos similares."]}
    out["evidence_id"] = ctx.add_ev("alternativas", "Alternativas observadas", {"alineaciones": by_al[:5], "companeros": team[:4]})
    return out


TOOLS = {
    "get_player_performance": (get_player_performance, "Métricas observadas del jugador del contexto en el partido: índice relativo, referencia, variabilidad, muestra y calidad.",
                               {"player_id": {"type": "integer"}, "game_id": {"type": "integer"}}, ["player_id", "game_id"]),
    "investigate_performance_change": (investigate_performance_change, "Investiga si hay una caída observable y consistente (ambos modos, mitades con bootstrap). Reconoce estabilidad o evidencia insuficiente.",
                                       {"player_id": {"type": "integer"}, "game_id": {"type": "integer"}}, ["player_id", "game_id"]),
    "find_relevant_plays": (find_relevant_plays, "Encuentra intervenciones útiles. criteria: lowest_index, highest_index, first_flag, reference_like, contrasting_context.",
                            {"player_id": {"type": "integer"}, "game_id": {"type": "integer"}, "criteria": {"type": "string", "enum": list(CRITERIA)}, "limit": {"type": "integer"}}, ["player_id", "game_id", "criteria"]),
    "compare_interventions": (compare_interventions, "Compara dos intervenciones reales del jugador (play_id_1 referencia, play_id_2 seleccionada): rapidez, desplazamiento, aceleración robusta y contexto.",
                              {"game_id": {"type": "integer"}, "play_id_1": {"type": "integer"}, "play_id_2": {"type": "integer"}, "ref_game_id": {"type": "integer"}}, ["game_id", "play_id_1", "play_id_2"]),
    "evaluate_available_alternatives": (evaluate_available_alternatives, "Alternativas realmente observadas (alineaciones del jugador, compañeros del mismo grupo) con muestras y limitaciones.",
                                        {"player_id": {"type": "integer"}, "game_id": {"type": "integer"}}, ["player_id", "game_id"]),
}


def tool_specs() -> list:
    return [{"toolSpec": {"name": n, "description": d, "inputSchema": {"json": {"type": "object", "properties": p, "required": r, "additionalProperties": False}}}}
            for n, (_, d, p, r) in TOOLS.items()]


def run_tool(ctx: Ctx, name: str, args: dict) -> dict:
    if name not in TOOLS:
        raise ToolError(f"Herramienta desconocida: {name}")
    fn, _, props, req = TOOLS[name]
    if not isinstance(args, dict) or set(args) - set(props) or any(k not in args for k in req):
        raise ToolError("Parámetros inválidos")
    clean_args = {}
    for k, v in args.items():
        t = props[k]["type"]
        if t == "integer":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
                raise ToolError(f"{k} debe ser entero")
            clean_args[k] = int(v)
        else:
            if not isinstance(v, str) or len(v) > 40:
                raise ToolError(f"{k} inválido")
            clean_args[k] = v
    return clean(fn(ctx, **clean_args))
