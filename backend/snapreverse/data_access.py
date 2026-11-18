"""Acceso y validación de datos. Solo lectura de data/. Caché limitada en memoria."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
import threading

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
TRACK_COLS = ["gameId", "playId", "nflId", "frameId", "time", "jerseyNumber", "team",
              "playDirection", "x", "y", "s", "a", "o", "dir", "event"]


class DataError(Exception):
    pass


class Tables:
    """Tablas pequeñas en memoria."""

    def __init__(self, data_dir: Path = DATA):
        self.dir = data_dir
        for n in ("games", "plays", "players", "pffScoutingData"):
            if not (data_dir / f"{n}.csv").exists():
                raise DataError(f"Falta {n}.csv en {data_dir}")
        self.games = pd.read_csv(data_dir / "games.csv")
        self.plays = pd.read_csv(data_dir / "plays.csv")
        self.players = pd.read_csv(data_dir / "players.csv")
        self.pff = pd.read_csv(data_dir / "pffScoutingData.csv")
        self._validate()
        self._cache: "OrderedDict[int, pd.DataFrame]" = OrderedDict()
        self._lock = threading.Lock()
        self.cache_size = 6

    def _validate(self) -> None:
        if self.games.gameId.duplicated().any():
            raise DataError("games.gameId duplicado")
        if self.plays.duplicated(["gameId", "playId"]).any():
            raise DataError("plays (gameId, playId) duplicado")
        if self.players.nflId.duplicated().any():
            raise DataError("players.nflId duplicado")
        if self.pff.duplicated(["gameId", "playId", "nflId"]).any():
            raise DataError("pff (gameId, playId, nflId) duplicado")

    def tracking_path(self, game_id: int) -> Path:
        gid = int(game_id)  # evita rutas arbitrarias
        p = self.dir / "tracking" / f"tracking_{gid}.csv"
        if not p.resolve().is_relative_to((self.dir / "tracking").resolve()):
            raise DataError("ruta inválida")
        return p

    def tracking(self, game_id: int, cols=None, cache: bool = True) -> pd.DataFrame:
        gid = int(game_id)
        with self._lock:
            if cache and gid in self._cache:
                self._cache.move_to_end(gid)
                return self._cache[gid]
        p = self.tracking_path(gid)
        if not p.exists():
            raise DataError(f"Sin tracking para el partido {gid}")
        df = pd.read_csv(p, usecols=cols or TRACK_COLS)
        if cache:
            with self._lock:
                self._cache[gid] = df
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
        return df


def clock_to_elapsed(quarter: int, clock: str) -> float:
    """Segundos de juego transcurridos (aprox. reloj; NO es descanso real)."""
    try:
        m, s = str(clock).split(":")
        rem = int(m) * 60 + int(s)
    except Exception:
        return float("nan")
    qlen = 900 if quarter <= 4 else 600
    base = min(quarter - 1, 4) * 900
    return float(base + qlen - rem)


def clean(o):
    """Convierte NaN/inf/numpy a tipos JSON válidos."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if (np.isnan(o) or np.isinf(o)) else round(float(o), 4)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if o is pd.NA or o is pd.NaT:
        return None
    return o
