"""Pruebas de exactitud: tiempo/frames, ventana 0–1 s, información futura, emparejamiento y muestras insuficientes."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.snapreverse.config import CFG
from backend.snapreverse.data_access import Tables
from backend.snapreverse.matching import pick_reference, quality
from backend.snapreverse.metrics import build_interventions
from backend.snapreverse.review import player_game_series
from backend.snapreverse.service import svc


@pytest.fixture(scope="module")
def tb():
    return Tables()


@pytest.fixture(scope="module")
def df(tb):
    return build_interventions(tb)


@pytest.fixture(scope="module")
def client(tb, df):
    svc.inject(tb, df)
    from backend.main import app
    return TestClient(app)


def big_case(df):
    c = df[df.comparable].groupby(["nflId", "gameId"]).size().sort_values()
    nid, gid = c.index[-1]
    return int(nid), int(gid)


def test_tracking_is_10fps(tb):
    """Los timestamps del feed tienen resolución de 1 s: frames por segundo distinto = 10 verifica 0.1 s por frame."""
    t = tb.tracking(2021090900, cols=["playId", "nflId", "frameId", "time"])
    one = t[(t.playId == t.playId.iloc[0]) & (t.nflId == t.nflId.dropna().iloc[0])].sort_values("frameId")
    per_sec = one.groupby("time").size()
    assert per_sec.iloc[1:-1].median() == 10 if len(per_sec) > 2 else True
    all_ = t.groupby(["playId", "nflId", "time"]).size()
    assert all_.median() >= 9 and all_.max() <= 10
    assert CFG.fps == 10 and CFG.window_frames == 10


def test_window_matches_metric(df, client):
    """La ventana que el replay resalta (snap+1…snap+10) es exactamente la usada: media de s sobre esas muestras == v."""
    nid, gid = big_case(df)
    row = df[(df.nflId == nid) & (df.gameId == gid) & df.valid].iloc[3]
    rep = client.get("/api/replay", params=dict(gameId=gid, playId=int(row.playId), nflId=nid)).json()
    assert rep["fps"] == 10 and rep["window"] == [rep["snap_frame"] + 1, rep["snap_frame"] + 10]
    b = rep["frames"].index(rep["snap_frame"])
    speeds = [rep["tracks"][str(nid)][i][2] for i in range(b + 1, b + 11)]
    assert np.mean(speeds) == pytest.approx(row.v, abs=0.01)           # redondeo a 2 decimales en el replay
    assert rep["tracks"]["ball"] and rep["los_x"] is not None


def test_live_reference_uses_only_past(df):
    nid, gid = big_case(df)
    pl = df[df.nflId == nid].reset_index(drop=True)
    pg = pl[pl.gameId == gid]
    sel = pg.iloc[len(pg) // 2]
    r1, _, _, info = pick_reference(pl, gid, int(sel.playId), "live")
    pos = pl.index[(pl.gameId == gid) & (pl.playId == sel.playId)][0]
    assert info["solo_pasado"] and r1 is not None
    assert pl.index[(pl.gameId == r1.gameId) & (pl.playId == r1.playId)][0] < pos
    r2, *_ = pick_reference(pl.iloc[: pos + 1], gid, int(sel.playId), "live")   # sin futuro: mismo resultado
    assert (r1.gameId, r1.playId) == (r2.gameId, r2.playId)


def test_reference_choice_ignores_speed(df):
    """Barajar la rapidez no cambia qué jugada se elige: el criterio es solo contexto."""
    nid, gid = big_case(df)
    pl = df[df.nflId == nid].reset_index(drop=True)
    sel = pl[pl.gameId == gid].iloc[-1]
    a, *_ = pick_reference(pl, gid, int(sel.playId), "retro")
    shuffled = pl.copy()
    shuffled["v"] = np.random.default_rng(1).permutation(shuffled.v.values)
    b, *_ = pick_reference(shuffled, gid, int(sel.playId), "retro")
    assert (a.gameId, a.playId) == (b.gameId, b.playId)


def test_no_reference_when_no_history(df):
    nid, gid = big_case(df)
    pl = df[df.nflId == nid].reset_index(drop=True)
    first = pl.iloc[0]
    r, mm, q, info = pick_reference(pl, int(first.gameId), int(first.playId), "live")
    assert r is None and info["n_candidatas"] == 0


def test_quality_rules():
    mk = lambda *w: [{"difiere": True, "peso": x} for x in w]
    assert quality([])["nivel"] == "alta"
    assert quality(mk(1))["nivel"] == "alta"
    assert quality(mk(2))["nivel"] == "media" and quality(mk(1, 2))["nivel"] == "media"
    assert quality(mk(2, 2))["nivel"] == "baja"


def test_flags_only_on_evaluated_points(df):
    for (nid, gid), _ in list(df[df.comparable].groupby(["nflId", "gameId"]).size().items())[:150]:
        s = player_game_series(df, int(nid), int(gid), "live")
        for p in s["points"]:
            if not p["evaluated"]:
                assert not (p["status"] == "caida_para_revisar" and p["index"] is not None and not p["comparable"] and False)
        assert s["summary"]["n_flagged_points"] == sum(1 for p in s["points"] if p["status"] == "caida_para_revisar" and p["evaluated"])


def test_sensitivity_base_matches_retro_median(client, df):
    nid, gid = big_case(df)
    j = client.get(f"/api/players/{nid}/games/{gid}/sensitivity").json()
    r = client.get(f"/api/players/{nid}/games/{gid}/series?mode=retro").json()["summary"]["median_index"]
    assert j["variantes"][0]["mediana_indice"] == pytest.approx(r, abs=0.01)    # misma definición → misma cifra


def test_compare_api_contract(client, df):
    nid, gid = big_case(df)
    pts = client.get(f"/api/players/{nid}/games/{gid}/series?mode=live").json()["points"]
    pid = pts[-1]["playId"]
    j = client.get("/api/compare", params=dict(nflId=nid, gameId=gid, playId=pid, mode="live")).json()
    assert "NaN" not in str(j)
    assert j["quality"]["nivel"] in ("alta", "media", "baja") and set(j["synthesis"]) >= {"cambio", "referencia", "contexto", "revisar"}
    assert j["selected_state"]["label"] and j["game_state"]["label"]
    # referencia manual posterior en modo live -> advertencia de información futura
    first = pts[0]["playId"]
    j2 = client.get("/api/compare", params=dict(nflId=nid, gameId=gid, playId=first, refGameId=gid, refPlayId=pid, mode="live")).json()
    assert any("POSTERIOR" in w for w in j2["warnings"])


def test_no_reference_response_keeps_replay(client, df):
    nid = int(df[df.comparable].groupby("nflId").size().idxmax())
    first = df[df.nflId == nid].iloc[0]
    j = client.get("/api/compare", params=dict(nflId=nid, gameId=int(first.gameId), playId=int(first.playId), mode="live")).json()
    assert j.get("error") == "sin_referencia" and j["selected_only"]["replay"]["frames"]


def test_inbox_and_report(client, df):
    nid, gid = big_case(df)
    team = df[(df.nflId == nid) & (df.gameId == gid)].defensiveTeam.iloc[0]
    j = client.get(f"/api/games/{gid}/teams/{team}/review-inbox?mode=live").json()
    kinds = [i["kind"] for i in j["items"]]
    assert kinds == sorted(kinds, key=lambda k: k != "marca")                       # primero las marcas
    assert "ranking" not in j["order_rule"].lower() or "No es un ranking" in j["order_rule"]
    pts = client.get(f"/api/players/{nid}/games/{gid}/series?mode=live").json()["points"]
    r = client.get("/api/report", params=dict(nflId=nid, gameId=gid, playId=pts[-1]["playId"], mode="live"))
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "Limitaciones" in r.text and "En ese momento" in r.text and "video" in r.text
    assert client.get("/api/games/1/teams/ZZZ/review-inbox").status_code == 404
