"""Pruebas: uniones, ventanas, referencias, casos con pocos datos y API (datos reales de solo lectura)."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.snapreverse.config import CFG
from backend.snapreverse.data_access import Tables, clean, clock_to_elapsed
from backend.snapreverse.metrics import build_interventions, game_interventions, reference
from backend.snapreverse.review import (STATUS_FLAG, STATUS_INS, STATUS_OK, point_status, player_game_series, smooth)
from backend.snapreverse.service import svc


@pytest.fixture(scope="module")
def tb():
    return Tables()


@pytest.fixture(scope="module")
def df(tb):
    return build_interventions(tb)


def synth_track(speeds, snap=6, n_frames=30):
    """Jugada sintética: 1 jugador con rapidez constante dada tras el snap."""
    rows = []
    for f in range(1, n_frames + 1):
        s = speeds if f > snap else 0.0
        rows.append(dict(gameId=1, playId=1, nflId=10, frameId=f, x=20 + (max(0, f - snap)) * s / 10, y=20.0, s=s,
                         event="ball_snap" if f == snap else "None"))
    return pd.DataFrame(rows)


def test_keys_unique(tb, df):
    assert not df.duplicated(["gameId", "playId", "nflId"]).any()
    assert len(df) <= (tb.pff.pff_role == "Pass Rush").sum()
    assert (df.pff_positionLinedUp.notna()).all()


def test_window_after_snap_only():
    t = synth_track(3.0)
    # velocidad alta después de la ventana no debe afectar; poner basura tras snap+10
    t.loc[t.frameId > 16, "s"] = 99.0
    pr = pd.DataFrame({"playId": [1], "nflId": [10]})
    r = game_interventions(t, pr).iloc[0]
    assert r.v == pytest.approx(3.0) and r.valid
    assert r.n_frames == CFG.window_frames


def test_no_snap_not_computed():
    t = synth_track(3.0); t["event"] = "None"
    out = game_interventions(t, pd.DataFrame({"playId": [1], "nflId": [10]}))
    assert out.empty  # sin snap no se calcula "desde el snap"


def test_short_play_excluded():
    t = synth_track(3.0, n_frames=10)
    r = game_interventions(t, pd.DataFrame({"playId": [1], "nflId": [10]})).iloc[0]
    assert not r.valid


def test_future_independent_live(df):
    nid, gid = df.groupby(["nflId", "gameId"]).size().sort_values().index[-1]
    s1 = player_game_series(df, nid, gid, "live")
    # eliminar todo lo posterior al 10º punto y comprobar que los 10 primeros no cambian
    pl = df[df.nflId == nid].reset_index(drop=True)
    pg = pl[pl.gameId == gid]
    cut_idx = pg.index[9]
    df2 = pd.concat([df[df.nflId != nid], pl.iloc[: cut_idx + 1]])
    s2 = player_game_series(df2, nid, gid, "live")
    for a, b in zip(s1["points"][:10], s2["points"][:10]):
        assert a["index"] == b["index"] and a["status"] == b["status"] and a["trend"] == b["trend"]


def test_reference_no_divide_zero():
    p = pd.DataFrame({"comparable": True, "gameId": [1] * 15 + [2] * 15, "group": "Interior", "v": 0.01})
    r = reference(p, "Interior")
    assert not r["ok"]


def test_reference_few_data():
    p = pd.DataFrame({"comparable": True, "gameId": [1, 1, 2], "group": "Borde", "v": [2.0, 2.1, 2.2]})
    assert not reference(p, "Borde")["ok"]
    assert point_status([80, 80, 80], reference(p, "Borde")) == STATUS_INS


def test_persistence_rule():
    ref = {"ok": True, "habit_pct": 5.0}
    assert point_status([100, 70, 70], ref) == STATUS_OK          # un solo bajo ... falta persistencia
    assert point_status([100, 70, 70, 70], ref) == STATUS_FLAG
    assert point_status([70, 70], ref) == STATUS_INS               # muestra insuficiente


def test_habit_raises_threshold():
    ref = {"ok": True, "habit_pct": 20.0}                         # umbral = 30
    assert point_status([80, 80, 80], ref) == STATUS_OK


def test_clean_nan():
    assert clean({"a": float("nan"), "b": [np.inf, np.float64(1.23456789)]}) == {"a": None, "b": [None, 1.2346]}
    assert clock_to_elapsed(1, "13:33") == 87.0


def test_smooth_live_uses_no_future():
    a = smooth([100, 90, 80, 70, 60], "live")
    b = smooth([100, 90, 80, 0, 0], "live")
    assert a[2] == b[2]


@pytest.fixture(scope="module")
def client(tb, df):
    svc.inject(tb, df)
    from backend.main import app
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_api_flow(client):
    d = client.get("/api/demo-case").json()
    s = client.get(f"/api/players/{d['nflId']}/games/{d['gameId']}/series?mode=live")
    assert s.status_code == 200 and "NaN" not in s.text
    j = s.json()
    assert j["participation"]["verified"] is False and j["points"]
    pid = j["points"][-1]["playId"]
    c = client.get("/api/compare", params=dict(nflId=d["nflId"], gameId=d["gameId"], playId=pid))
    assert c.status_code == 200 and "NaN" not in c.text
    cj = c.json()
    assert cj["sync"] == "ball_snap" and cj["selected"]["replay"]["snap_frame"] is not None
    r = client.get("/api/replay", params=dict(gameId=d["gameId"], playId=pid, nflId=d["nflId"]))
    assert r.status_code == 200 and "ball" in r.json()["tracks"]
    assert client.get(f"/api/players/{d['nflId']}/games/{d['gameId']}/sensitivity").status_code == 200


def test_api_errors(client):
    assert client.get("/api/players/1/games/2/series").status_code == 404
    assert client.get("/api/players/1/games/2/series?mode=x").status_code == 422
    assert client.get("/api/replay", params=dict(gameId=999, playId=1, nflId=1)).status_code == 404
    assert client.get("/api/games/2021090900/teams/ZZZ/players").status_code == 404
