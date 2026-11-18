"""Estado de la aplicación: carga al arrancar (en hilo) y consultas de alto nivel."""
from __future__ import annotations

import threading

import numpy as np
import pandas as pd

from .config import CFG
from .data_access import Tables, clean
from .metrics import build_interventions, reference
from .matching import pick_reference, mismatches, quality, prep
from .replay import build_replay, context_diff
from .review import player_game_series, review_card, STATUS_LABEL, STATUS_FLAG, _ctx, _threshold


class Service:
    def __init__(self):
        self.ready = False
        self.error: str | None = None
        self.tb: Tables | None = None
        self.df: pd.DataFrame | None = None
        self.demo: dict | None = None
        self.demos: dict = {}
        self.demo_ready = False
        self._inbox: dict = {}
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._load, daemon=True)
        self._thread.start()

    def load_sync(self):
        self._load()

    def _load(self):
        try:
            self.tb = Tables()
            self.df = build_interventions(self.tb)
            self.ready = True  # la app ya sirve; los casos demo se calculan enseguida en este mismo hilo
            self.demos = self._pick_demos(); self.demo = self.demos.get('signal') or (list(self.demos.values())[0] if self.demos else None)
            self.demo_ready = True
        except Exception as e:  # pragma: no cover
            self.error = f"{type(e).__name__}: {e}"

    def inject(self, tb: Tables, df: pd.DataFrame):  # para pruebas
        self.tb, self.df, self.ready = tb, df, True
        self.demo_ready = True
        self.demos = self._pick_demos(); self.demo = self.demos.get('signal') or (list(self.demos.values())[0] if self.demos else None)

    # ------------------------------------------------------------------
    def status(self) -> dict:
        d = {"ready": self.ready, "demo_ready": self.demo_ready, "error": self.error, "exposure_verified": False}
        if self.ready:
            d.update(n_interventions=int(len(self.df)), n_games=int(self.df.gameId.nunique()),
                     n_players=int(self.df.nflId.nunique()), season=int(self.tb.games.season.iloc[0]))
        return d

    def games(self) -> list:
        g = self.df.groupby("gameId").agg(teams=("defensiveTeam", lambda s: sorted(set(s))), n=("playId", "size")).reset_index()
        m = self.tb.games.merge(g, on="gameId")
        m = m.sort_values(["week", "gameDate", "gameTimeEastern"])
        return [{"gameId": int(r.gameId), "week": int(r.week), "date": r.gameDate, "home": r.homeTeamAbbr,
                 "away": r.visitorTeamAbbr, "teams": r.teams, "n_interventions": int(r.n)} for r in m.itertuples()]

    def players(self, game_id: int, team: str) -> list | None:
        d = self.df[(self.df.gameId == game_id) & (self.df.defensiveTeam == team)]
        if d.empty:
            return None
        names = self.tb.players.set_index("nflId")
        out = []
        for nid, g in d.groupby("nflId"):
            out.append({"nflId": int(nid), "name": names.displayName.get(nid, str(nid)), "pos": names.officialPosition.get(nid),
                        "n_obs": int(len(g)), "n_comparable": int(g.comparable.sum()),
                        "evaluable": bool(g.comparable.sum() >= CFG.min_game_obs),
                        "total_obs": int((self.df.nflId == nid).sum()),
                        "total_games": int(self.df[self.df.nflId == nid].gameId.nunique())})
        return sorted(out, key=lambda r: -r["n_obs"])

    def series(self, nfl_id: int, game_id: int, mode: str) -> dict | None:
        if not ((self.df.nflId == nfl_id) & (self.df.gameId == game_id)).any():
            return None
        s = player_game_series(self.df, nfl_id, game_id, mode)
        names = self.tb.players.set_index("nflId")
        s["player"] = {"nflId": nfl_id, "name": names.displayName.get(nfl_id), "pos": names.officialPosition.get(nfl_id)}
        s["review"] = review_card(s, mode)
        g = self.tb.games[self.tb.games.gameId == game_id].iloc[0]
        s["game"] = {"gameId": game_id, "week": int(g.week), "home": g.homeTeamAbbr, "away": g.visitorTeamAbbr, "date": g.gameDate}
        s["participation"] = {"verified": False, "note": "No hay participación individual verificada: solo 'intervenciones observadas' (Pass Rush en jugadas de pase con tracking). No se afirma carga acumulada ni descanso."}
        return s

    def replay(self, game_id, play_id, nfl_id):
        return build_replay(self.tb, game_id, play_id, nfl_id)

    def compare(self, nfl_id: int, game_id: int, play_sel: int, ref_game: int | None, ref_play: int | None, mode: str):
        pl = self.df[self.df.nflId == nfl_id].reset_index(drop=True)
        sel = pl[(pl.gameId == game_id) & (pl.playId == play_sel)]
        if sel.empty:
            return None
        sel = sel.iloc[0]
        ser = player_game_series(self.df, nfl_id, game_id, mode)
        sp = next(p for p in ser["points"] if p["playId"] == play_sel)
        auto = ref_play is None
        warn, info = [], {}
        if auto:
            r, mm, q, info = pick_reference(pl, game_id, play_sel, mode)
            if r is None:
                rep = self.replay(game_id, play_sel, nfl_id)
                return {"error": "sin_referencia", "message": info.get("motivo", "Sin referencia comparable"), "selected_only": {"point": sp, "replay": rep, "gameId": game_id}}
            ref_game, ref_play = int(r.gameId), int(r.playId)
        else:
            rr = pl[(pl.gameId == ref_game) & (pl.playId == ref_play)]
            if rr.empty:
                return None
            r = prep(pl)[(pl.gameId == ref_game) & (pl.playId == ref_play)].iloc[0]
            s_ = prep(pl)[(pl.gameId == game_id) & (pl.playId == play_sel)].iloc[0]
            mm = mismatches(r, s_); q = quality(mm)
            if mode == "live" and r.gpos > s_.gpos:
                warn.append("La referencia elegida es POSTERIOR a la jugada: en modo «en ese momento» eso usa información futura.")
            if not r.comparable:
                warn.append("La referencia elegida no es comparable (play action o ventana incompleta).")
        a, b = self.replay(int(ref_game), ref_play, nfl_id), self.replay(game_id, play_sel, nfl_id)
        rp = {"playId": ref_play, "gameId": int(ref_game), "v": float(r.v) if r.valid else None, "disp": float(r.disp) if r.valid else None,
              "index_vs_ref_propia": (100 * float(r.v) / sp["v_ref"]) if (r.valid and sp["v_ref"] and sp["v_ref"] >= CFG.min_ref_speed) else None,
              "elapsed": float(r.elapsed), "ctx": _ctx(r), "comparable": bool(r.comparable)}
        if sp["ctx"]["play_action"] != rp["ctx"]["play_action"]: warn.append("Una jugada es play action y la otra no.")
        if a["snap_frame"] is None or b["snap_frame"] is None: warn.append("Falta snap en una jugada: no hay sincronización común.")
        if info.get("aviso"): warn.append(info["aviso"])
        seq = self._sequence(ser, sp)
        out = {"reference": {"point": rp, "replay": a, "gameId": int(ref_game)}, "selected": {"point": sp, "replay": b, "gameId": game_id},
               "context": context_diff(rp["ctx"], sp["ctx"]), "mismatches": mm, "quality": q, "match_info": info, "warnings": warn, "reference_auto": auto,
               "reference_rule": info.get("criterio") or "Elegida manualmente por el usuario.", "sync": "ball_snap", "mode": mode, "sequence": seq,
               "selected_state": {"status": sp["status"], "label": STATUS_LABEL[sp["status"]]}, "game_state": {"status": ser["summary"]["status"], "label": ser["summary"]["status_label"]}}
        out["synthesis"] = self._synthesis(ser, sp, rp, seq, mm, q, mode)
        return out

    def _sequence(self, ser: dict, sp: dict) -> dict:
        """Secuencia de hasta 3 intervenciones comparables que terminan en la jugada seleccionada (solo pasado)."""
        cmp_pts = [p for p in ser["points"] if p["comparable"] and p["index"] is not None and p["order"] <= sp["order"]]
        last = cmp_pts[-CFG.persistence:]
        T = _threshold(sp["habit_pct"])
        below = [p for p in last if p["index"] < 100 - T]
        return {"plays": [{"playId": p["playId"], "index": p["index"], "reloj": f"Q{p['ctx']['cuarto']} {p['ctx']['reloj']}"} for p in last],
                "mean_index": float(np.mean([p["index"] for p in last])) if last else None, "n_below": len(below), "of": len(last),
                "threshold_index": 100 - T, "persistent": len(last) == CFG.persistence and len(below) == CFG.persistence}

    def _synthesis(self, ser, sp, rp, seq, mm, q, mode) -> dict:
        sm = ser["summary"]
        diffs = [m["factor"] for m in mm if m["difiere"]]
        lines = {}
        if sp["index"] is None:
            lines["cambio"] = "Esta jugada no tiene índice (sin referencia suficiente o no comparable): " + (sp["excl_reason"] or "referencia insuficiente") + "."
        else:
            lines["cambio"] = (f"En la jugada {sp['playId']} (Q{sp['ctx']['cuarto']} {sp['ctx']['reloj']}) su rapidez 0–1 s fue {sp['v']:.2f} yd/s: índice {sp['index']:.0f} "
                               f"respecto a su referencia de {sp['v_ref']:.2f} yd/s.")
        if seq["of"]:
            lines["magnitud_persistencia"] = (f"Secuencia de {seq['of']} intervenciones comparables hasta esta jugada: índice medio {seq['mean_index']:.0f}; "
                                             f"{seq['n_below']} de {seq['of']} por debajo del umbral ({seq['threshold_index']:.0f}). " + ("Cumple la regla de persistencia." if seq["persistent"] else "No cumple la regla de persistencia (se exigen 3 seguidas)."))
        lines["referencia"] = (f"Referencia ({'fija: toda su historia' if mode == 'retro' else 'creciente: solo intervenciones previas'}): mediana propia {sp['v_ref']:.2f} yd/s, n={sp['ref_n']} intervenciones en {sp['ref_games']} partido(s)."
                               if sp["v_ref"] else "Referencia insuficiente para esta jugada.")
        lines["contexto"] = (f"Jugada comparada: {rp['playId']}. Calidad de comparación {q['nivel']}; difieren: {', '.join(diffs) if diffs else 'ningún factor clave'}.")
        lines["revisar"] = ["Ver ambas jugadas sincronizadas al snap y comprobar si hubo contención, stunt, cobertura o doble bloqueo.",
                            "Confirmar en video si la diferencia de salida coincide con las diferencias de contexto listadas."]
        lines["estado_nota"] = (f"Estado de esta jugada: {STATUS_LABEL[sp['status']]}. Estado al final del partido: {sm['status_label']}. "
                                "El estado final puede ser normal aunque una jugada o secuencia intermedia haya sido baja.")
        return lines

    def sensitivity(self, nfl_id: int, game_id: int) -> dict | None:
        """Cómo cambia la mediana del índice del partido con decisiones de referencia (todas en retrospectivo, universo = intervenciones comparables)."""
        if not ((self.df.nflId == nfl_id) & (self.df.gameId == game_id)).any():
            return None
        pl = self.df[self.df.nflId == nfl_id]
        pg = pl[(pl.gameId == game_id) & pl.comparable]
        allc, other = pl[pl.comparable], pl[pl.comparable & (pl.gameId != game_id)]
        def variant(label, refs, col="v", desc=""):
            idx, rv = [], []
            for _, r in pg.iterrows():
                rf = refs(r)
                if rf is not None and rf == rf and rf >= CFG.min_ref_speed:
                    idx.append(100 * r[col] / rf); rv.append(rf)
            return {"variante": label, "mediana_indice": float(np.median(idx)) if idx else None, "v_ref_tipica": float(np.median(rv)) if rv else None, "n": len(idx), "descripcion": desc}
        cache = {}
        def base_ref(r):
            if r.group not in cache: cache[r.group] = reference(pl, r.group, CFG)["v_ref"]
            return cache[r.group]
        rows = [variant("Base (modo retrospectivo)", base_ref, desc="Mediana propia, por grupo de alineación si hay muestra; toda su historia del dataset."),
                variant("Mediana de todas sus intervenciones", lambda r: allc.v.median(), desc="Sin separar por grupo de alineación."),
                variant("Media en lugar de mediana", lambda r: allc.v.mean(), desc="Sensible a salidas extremas."),
                variant("Solo otros partidos", lambda r: other.v.median() if len(other) else None, desc="Excluye este partido de la referencia."),
                variant("Incluyendo play action en la referencia", lambda r: pl[pl.valid].v.median(), desc="Mezcla contextos de salida distintos."),
                variant("Desplazamiento a 1 s", lambda r: allc.disp.median(), col="disp", desc="Métrica alternativa; correlaciona 0.99 con la rapidez.")]
        live = player_game_series(self.df, nfl_id, game_id, "live")["summary"]
        retro = player_game_series(self.df, nfl_id, game_id, "retro")["summary"]
        return {"variantes": rows, "modos": {"live": {"mediana_indice": live["median_index"], "ref_final": live["v_ref"], "ref_n": live["ref_n"]},
                                             "retro": {"mediana_indice": retro["median_index"], "ref_final": retro["v_ref"], "ref_n": retro["ref_n"]}},
                "nota": "La referencia mostrada en las tarjetas depende del modo: en «en ese momento» crece con cada intervención (solo pasado; la tarjeta muestra la del último punto); en «retrospectivo» es fija. "
                        "Por eso pueden diferir de esta tabla, cuya base es retrospectiva y usa el grupo de alineación de cada jugada. 100 siempre = la referencia de esa fila."}

    # ------------------------------------------------------------------ bandeja de revisión
    def inbox(self, game_id: int, team: str, mode: str) -> dict | None:
        key = (game_id, team, mode)
        if key in self._inbox: return self._inbox[key]
        d = self.df[(self.df.gameId == game_id) & (self.df.defensiveTeam == team)]
        if d.empty: return None
        names = self.tb.players.set_index("nflId")
        items, insufficient, evaluated = [], 0, 0
        for nid in d.nflId.unique():
            nid = int(nid)
            ser = player_game_series(self.df, nid, game_id, mode)
            sm = ser["summary"]
            pts = [p for p in ser["points"] if p["comparable"] and p["index"] is not None]
            if sm["n_comparable"] < CFG.min_game_obs or not pts:
                insufficient += 1; continue
            evaluated += 1
            flagged = [p for p in ser["points"] if p["status"] == STATUS_FLAG and p["evaluated"]]
            T = sm["threshold_pts"]
            base = {"nflId": nid, "name": names.displayName.get(nid, str(nid)), "pos": names.officialPosition.get(nid), "n_comparable": sm["n_comparable"],
                    "ref_n": sm["ref_n"], "ref_games": sm["ref_games"], "threshold_index": 100 - T}
            if flagged:
                last_i = max(pts.index(next(q for q in pts if q["playId"] == f["playId"])) for f in flagged)
                first_i = min(pts.index(next(q for q in pts if q["playId"] == f["playId"])) for f in flagged)
                seq = pts[max(0, first_i - CFG.persistence + 1): last_i + 1]
                retro_also = None
                if mode == "live":
                    retro_also = player_game_series(self.df, nid, game_id, "retro")["summary"]["n_flagged_points"] > 0
                items.append({**base, "kind": "marca", "playId": flagged[0]["playId"], "plays": [p["playId"] for p in seq], "n_plays": len(seq),
                              "mean_index": float(np.mean([p["index"] for p in seq])), "reloj": f"Q{flagged[0]['ctx']['cuarto']} {flagged[0]['ctx']['reloj']}", "retro_also": retro_also})
            else:
                best = None
                for i in range(len(pts) - CFG.persistence + 1):
                    w = pts[i:i + CFG.persistence]; m = float(np.mean([p["index"] for p in w]))
                    if best is None or m < best[0]: best = (m, w)
                if best and best[0] < 100 - 0.6 * T:
                    items.append({**base, "kind": "cerca", "playId": best[1][-1]["playId"], "plays": [p["playId"] for p in best[1]], "n_plays": len(best[1]),
                                  "mean_index": best[0], "reloj": f"Q{best[1][-1]['ctx']['cuarto']} {best[1][-1]['ctx']['reloj']}", "retro_also": None})
        items.sort(key=lambda x: (x["kind"] != "marca", -x["n_plays"], x["mean_index"], -x["ref_n"]))
        out = {"mode": mode, "items": items[:8], "evaluated": evaluated, "insufficient": insufficient,
               "order_rule": "Primero secuencias que cumplen la regla (marca), luego las cercanas al umbral; dentro de cada grupo: más intervenciones consecutivas, menor índice medio, mayor muestra de referencia. No es un ranking de salud ni de fatiga."}
        if len(self._inbox) > 64: self._inbox.pop(next(iter(self._inbox)))
        self._inbox[key] = out
        return out

    # ------------------------------------------------------------------ reporte
    def report_md(self, nfl_id: int, game_id: int, play_id: int, mode: str) -> str | None:
        cmp = self.compare(nfl_id, game_id, play_id, None, None, mode)
        if cmp is None: return None
        ser = self.series(nfl_id, game_id, mode)
        sm, rv = ser["summary"], ser["review"]
        L = [f"# SnapReverse — Reporte de revisión", "",
             f"- **Jugador:** {ser['player']['name']} ({ser['player']['pos']})", f"- **Partido:** {ser['game']['away']} @ {ser['game']['home']} · semana {ser['game']['week']} ({ser['game']['date']})",
             f"- **Modo:** {rv.get('mode_label', mode)}", ""]
        if cmp.get("error"):
            L += ["## Secuencia", f"No hay referencia comparable: {cmp['message']}", ""]
        else:
            s = cmp["selected"]["point"]; syn = cmp["synthesis"]
            L += ["## Secuencia seleccionada", f"- Jugada {s['playId']} · Q{s['ctx']['cuarto']} {s['ctx']['reloj']} · índice {s['index'] if s['index'] is None else round(s['index'])} · rapidez 0–1 s {s['v']:.2f} yd/s" if s["v"] else f"- Jugada {s['playId']}",
                  f"- {syn['cambio']}", f"- {syn.get('magnitud_persistencia', '')}", f"- {syn['referencia']}", f"- {syn['estado_nota']}", "",
                  f"## Comparación (jugada de referencia {cmp['reference']['point']['playId']})", f"- Calidad de comparación: **{cmp['quality']['nivel']}** — {cmp['quality']['regla']}", "- Diferencias de contexto:"]
            L += [f"  - {m['factor']}: referencia {m['referencia']} / seleccionada {m['seleccionada']}" for m in cmp["mismatches"] if m["difiere"]] or ["  - Ninguna en los factores clave."]
            L += [f"- Advertencias: {'; '.join(cmp['warnings'])}" if cmp["warnings"] else "- Advertencias: ninguna", ""]
        L += ["## Resumen del partido", f"- Índice mediano {sm['median_index'] and round(sm['median_index'])} (100 = su referencia) · {sm['n_comparable']} intervenciones comparables de {sm['n_obs']} · referencia {sm['v_ref'] and round(sm['v_ref'], 2)} yd/s (n={sm['ref_n']}, {sm['ref_games']} partidos)",
              f"- Estado al final del partido: {sm['status_label']} · puntos con marca: {sm['n_flagged_points']}", "", "## Qué revisar"]
        L += [f"- {x}" for x in rv["revisar"]]
        L += ["", "## Limitaciones", "- Mide rapidez observada 0–1 s tras el snap; no mide fatiga, energía ni lesiones y no predice el efecto de una sustitución.",
              "- Participación y descanso no verificados; solo intervenciones observadas (Pass Rush en jugadas de pase).",
              "- Umbrales heurísticos configurables, no validados médica ni deportivamente. Sin etiquetas humanas: no hay precisión/recall.",
              "- Este reporte no incluye video; solo datos de tracking."]
        return "\n".join(L)

    # ------------------------------------------------------------------ casos demo
    def _pick_demos(self) -> dict:
        df = self.df
        c = df[df.comparable].groupby(["nflId", "gameId"]).size(); c = c[c >= 10]
        names = self.tb.players.set_index("nflId").displayName
        live = {}
        for (nid, gid), n in c.items():
            s = player_game_series(df, int(nid), int(gid), "live")["summary"]
            live[(int(nid), int(gid))] = (int(n), s)
        flagged = [(k, v) for k, v in live.items() if v[1]["n_flagged_points"] > 0]
        rob = []
        for k, (n, s) in flagged:
            r = player_game_series(df, k[0], k[1], "retro")["summary"]
            rob.append((k, n, s, r))
        def pack(kind, title, k, n, s, r, crit):
            team = df[(df.nflId == k[0]) & (df.gameId == k[1])].defensiveTeam.iloc[0]
            g = self.tb.games[self.tb.games.gameId == k[1]].iloc[0]
            return {"kind": kind, "title": title, "nflId": k[0], "gameId": k[1], "team": team, "name": names.get(k[0]), "week": int(g.week),
                    "playId": s["first_flag_playId"], "n_comparable": n, "flags_live": s["n_flagged_points"], "flags_retro": None if r is None else r["n_flagged_points"],
                    "median_index_live": s["median_index"], "ref_n": s["ref_n"], "criterio": crit}
        demos = {}
        both = [x for x in rob if x[3]["n_flagged_points"] > 0]
        if both:
            k, n, s, r = max(both, key=lambda x: (min(x[2]["n_flagged_points"], x[3]["n_flagged_points"]), x[2]["ref_n"], x[1]))
            demos["signal"] = pack("signal", "Señal que persiste al cambiar de referencia", k, n, s, r, "Marca en ambos modos; mayor persistencia mínima, luego mayor muestra de referencia.")
        elif rob:
            k, n, s, r = max(rob, key=lambda x: (x[2]["n_flagged_points"], x[2]["ref_n"]))
            demos["signal"] = pack("signal", "Señal solo «en ese momento» (no robusta)", k, n, s, r, "Sin casos con marca en ambos modos; se muestra la de mayor persistencia y se declara que no es robusta.")
        quiet = [(k, v) for k, v in live.items() if v[1]["n_flagged_points"] == 0 and v[1]["ref_n"] >= 30 and v[0] >= 25 and v[1]["median_index"] is not None]
        if quiet:
            k, v = min(quiet, key=lambda kv: abs(kv[1][1]["median_index"] - 100))
            demos["normal"] = pack("normal", "Variación normal", k, v[0], v[1], None, "Sin marcas; ≥25 intervenciones comparables y referencia ≥30; índice mediano más cercano a 100.")
            demos["normal"]["playId"] = None
        best = None
        for k, n, s, r in rob:
            sel_p = s["first_flag_playId"]
            pl = df[df.nflId == k[0]].reset_index(drop=True)
            rr, mm, q, _ = pick_reference(pl, k[1], sel_p, "live")
            if rr is None: continue
            keyd = [m["factor"] for m in mm if m["difiere"] and m["factor"] in ("Bloqueadores asignados", "Número de rushers", "Alineación exacta")]
            if keyd and (best is None or len(keyd) > best[0]): best = (len(keyd), k, n, s, r, keyd)
        if best:
            demos["context"] = pack("context", "Caída con diferencias de contexto relevantes", best[1], best[2], best[3], best[4], "Marca «en ese momento» cuya referencia automática difiere en bloqueadores, rushers o alineación exacta (más diferencias).")
            demos["context"]["context_diffs"] = best[5]
        return demos


svc = Service()
