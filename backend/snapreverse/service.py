"""Estado de la aplicación: carga al arrancar (en hilo) y consultas de alto nivel."""
from __future__ import annotations

import threading

import numpy as np
import pandas as pd

from .config import CFG
from .data_access import Tables, clean
from .metrics import build_interventions, reference
from .replay import build_replay, context_diff, default_reference
from .review import player_game_series, review_card, STATUS_LABEL


class Service:
    def __init__(self):
        self.ready = False
        self.error: str | None = None
        self.tb: Tables | None = None
        self.df: pd.DataFrame | None = None
        self.demo: dict | None = None
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
            self.demo = self._pick_demo()
            self.ready = True
        except Exception as e:  # pragma: no cover
            self.error = f"{type(e).__name__}: {e}"

    def inject(self, tb: Tables, df: pd.DataFrame):  # para pruebas
        self.tb, self.df, self.ready = tb, df, True
        self.demo = self._pick_demo()

    # ------------------------------------------------------------------
    def status(self) -> dict:
        d = {"ready": self.ready, "error": self.error, "exposure_verified": False}
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
        if auto:
            r = default_reference(pl, sel, sp["v_ref"], play_sel)
            if r is None:
                return {"error": "sin_referencia", "message": "No hay jugada de referencia comparable (mismo grupo de alineación, sin play action)."}
            ref_game, ref_play = int(r.gameId), int(r.playId)
        rr = pl[(pl.gameId == ref_game) & (pl.playId == ref_play)]
        if rr.empty:
            return None
        rr = rr.iloc[0]
        rg = player_game_series(self.df, nfl_id, int(ref_game), mode)
        rp = next(p for p in rg["points"] if p["playId"] == ref_play)
        a, b = self.replay(int(ref_game), ref_play, nfl_id), self.replay(game_id, play_sel, nfl_id)
        warn = []
        if sp["ctx"]["play_action"] != rp["ctx"]["play_action"]: warn.append("Una jugada es play action y la otra no.")
        if sp["ctx"]["grupo_alineacion"] != rp["ctx"]["grupo_alineacion"]: warn.append("Distinto grupo de alineación.")
        if a["snap_frame"] is None or b["snap_frame"] is None: warn.append("Falta snap en una jugada: no hay sincronización común.")
        return {"reference": {"point": rp, "replay": a, "gameId": int(ref_game)}, "selected": {"point": sp, "replay": b, "gameId": game_id},
                "context": context_diff(rp["ctx"], sp["ctx"]), "warnings": warn, "reference_auto": auto,
                "reference_rule": "Jugada comparable (sin play action, mismo grupo de alineación) con rapidez más cercana a su mediana propia; criterio fijo, no elegido para exagerar caídas.",
                "sync": "ball_snap"}

    def sensitivity(self, nfl_id: int, game_id: int) -> dict | None:
        """Cómo cambian los resultados al variar decisiones importantes."""
        if not ((self.df.nflId == nfl_id) & (self.df.gameId == game_id)).any():
            return None
        pl = self.df[self.df.nflId == nfl_id]
        pg = pl[(pl.gameId == game_id) & pl.comparable]
        out = []
        def idx_stats(refv, label, v):
            if refv is None or refv < CFG.min_ref_speed or len(v) == 0:
                out.append({"variante": label, "mediana_indice": None, "nota": "Referencia no válida"}); return
            out.append({"variante": label, "mediana_indice": float(np.median(100 * v / refv)), "v_ref": float(refv)})
        base = reference(pl, pg.group.mode().iloc[0] if len(pg) else "", CFG)
        idx_stats(base["v_ref"], "Referencia base (mediana, por grupo)", pg.v.values)
        allc = pl[pl.comparable]
        idx_stats(float(allc.v.median()) if len(allc) else None, "Mediana de todas sus intervenciones", pg.v.values)
        idx_stats(float(allc.v.mean()) if len(allc) else None, "Media en lugar de mediana", pg.v.values)
        other = allc[allc.gameId != game_id]
        idx_stats(float(other.v.median()) if len(other) else None, "Referencia solo de otros partidos", pg.v.values)
        pa = pl[pl.valid]
        idx_stats(float(pa.v.median()) if len(pa) else None, "Incluyendo play action en la referencia", pg.v.values)
        d = pl[pl.comparable]; 
        idx_stats(float(d.disp.median()) if len(d) else None, "Desplazamiento 1 s (en vez de rapidez)", pg.disp.values)
        return {"variantes": out, "nota": "Se compara cómo cambia la mediana del índice del partido; la rapidez y el desplazamiento correlacionan 0.99 en estos datos, por eso solo se usa la rapidez."}

    def _pick_demo(self) -> dict | None:
        """Caso con más intervenciones comparables entre los marcados en modo retrospectivo; si no hay, el de más datos."""
        c = self.df[self.df.comparable].groupby(["nflId", "gameId"]).size()
        c = c[c >= 12].sort_values(ascending=False)
        if c.empty:
            return None
        flagged = None
        for (nid, gid), n in c.head(300).items():
            s = player_game_series(self.df, int(nid), int(gid), "live")["summary"]
            if s["n_flagged_points"] > 0:
                flagged = (int(nid), int(gid), int(n), s["n_flagged_points"]); break
        nid, gid, n = (flagged[:3] if flagged else (int(c.index[0][0]), int(c.index[0][1]), int(c.iloc[0])))
        g = self.tb.games[self.tb.games.gameId == gid].iloc[0]
        team = self.df[(self.df.nflId == nid) & (self.df.gameId == gid)].defensiveTeam.iloc[0]
        return {"nflId": nid, "gameId": gid, "team": team, "n_comparable": n, "has_flag_live": flagged is not None,
                "name": self.tb.players.set_index("nflId").displayName.get(nid), "week": int(g.week),
                "criterio": "Mayor número de intervenciones comparables entre casos con al menos una marca en modo 'en ese momento'; si no hay marcas, el de más datos."}


svc = Service()
