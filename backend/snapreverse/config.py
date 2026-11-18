"""Parámetros heurísticos configurables (NO son límites médicos validados)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    window_frames: int = 10          # 10 fps -> 1.0 s después del snap
    fps: int = 10
    min_ref_speed: float = 0.8       # yd/s; referencias menores no producen índice
    min_ref_n: int = 12              # intervenciones previas para referencia suficiente
    min_ref_games: int = 2           # partidos distintos en la referencia
    group_ref_min_n: int = 8         # mínimo por grupo de alineación para usar referencia por grupo
    persistence: int = 3             # intervenciones consecutivas observadas bajo el umbral
    drop_pct: float = 15.0           # caída mínima (puntos de índice) para revisar
    habit_mult: float = 1.5          # el umbral sube si la variación habitual es mayor
    min_game_obs: int = 3            # observaciones en el partido para evaluar
    smooth_window: int = 3           # media móvil centrada (puntos)
    gap_plays: int = 2               # jugadas defensivas seguidas sin observación = intervalo sin observación


CFG = Config()

TERMINAL_EVENTS = {"pass_forward", "autoevent_passforward", "qb_sack", "qb_strip_sack",
                   "run", "handoff", "fumble", "pass_shovel", "qb_spike"}
SNAP_EVENTS = ("ball_snap", "autoevent_ballsnap")

ALIGN_GROUP = {
    "DLT": "Interior", "DRT": "Interior", "NT": "Interior", "NRT": "Interior", "NLT": "Interior",
    "LEO": "Borde", "REO": "Borde", "LE": "Borde", "RE": "Borde",
    "LOLB": "Borde (OLB)", "ROLB": "Borde (OLB)",
}
DEFAULT_GROUP = "Otra (LB/DB)"
