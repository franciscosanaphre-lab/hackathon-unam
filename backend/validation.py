"""Evaluación exploratoria SIN etiquetas humanas (no hay ground truth: no se reporta precisión ni recall).
Ejecuta:  .venv/bin/python -m backend.validation   -> imprime y escribe VALIDACION.md
Reporta cobertura, frecuencia de alertas, suficiencia de evidencia, sensibilidad a parámetros y comparación con un baseline simple."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd

from .snapreverse.config import CFG
from .snapreverse.review import STATUS_FLAG, STATUS_INS, player_game_series
from .snapreverse.service import svc


def run(df: pd.DataFrame, cfg, mode: str, cases) -> dict:
    out = {}
    for n, g in cases:
        s = player_game_series(df, n, g, mode, cfg)
        pts = s["points"]
        out[(n, g)] = {"flag": any(p["status"] == STATUS_FLAG and p["evaluated"] for p in pts),
                       "evaluable": any(p["status"] != STATUS_INS for p in pts), "pts": pts}
    return out


def baseline(df: pd.DataFrame, cases) -> dict:
    """Baseline simple y explícito: referencia = media de la rapidez de TODAS sus jugadas previas válidas (sin separar alineación,
    sin excluir play action, sin escalar el umbral por variabilidad); marca si las últimas 3 están todas <85% de esa referencia (≥10 previas)."""
    out = {}
    for n, g in cases:
        pl = df[(df.nflId == n)].reset_index(drop=True)
        pg = pl[pl.gameId == g]
        flag, pa_involved = False, False
        for pos in pg.index:
            prev = pl.iloc[:pos]; prev = prev[prev.valid]
            if len(prev) < 10: continue
            ref = prev.v.mean()
            if ref < CFG.min_ref_speed: continue
            cur = pl.iloc[:pos + 1]; cur = cur[(cur.gameId == g) & cur.valid].tail(3)
            if len(cur) == 3 and (cur.v < 0.85 * ref).all():
                flag = True; pa_involved = pa_involved or bool((cur.pff_playAction == 1).any())
                break
        out[(n, g)] = {"flag": flag, "pa": pa_involved}
    return out


def main():
    svc.load_sync()
    df = svc.df
    comp = df[df.comparable].groupby(["nflId", "gameId"]).size()
    allpg = df.groupby(["nflId", "gameId"]).size()
    cases = [k for k, v in comp.items() if v >= CFG.min_game_obs]
    L = ["# Validación exploratoria de SnapReverse", "",
         "> **No hay etiquetas humanas ni ground truth** (nadie marcó qué secuencias «merecían» revisión). Por eso **no se reporta precisión, recall ni «detección correcta»**. "
         "Lo siguiente describe comportamiento del método: cobertura, frecuencia de alertas, estabilidad ante parámetros y comparación con un baseline. Todo es **exploratorio** y no prueba utilidad deportiva ni causalidad.", "",
         "## 1. Corrección (pruebas automáticas)", "Ver `backend/tests/`: conversión frame↔tiempo, ventana 0–1 s, ausencia de información futura, referencia/índice, emparejamiento y muestras insuficientes.", ""]
    live, retro = run(df, CFG, "live", cases), run(df, CFG, "retro", cases)
    nflag_l, nflag_r = sum(v["flag"] for v in live.values()), sum(v["flag"] for v in retro.values())
    both = sum(live[k]["flag"] and retro[k]["flag"] for k in cases)
    ev_l = sum(v["evaluable"] for v in live.values()); ev_r = sum(v["evaluable"] for v in retro.values())
    teamgames = df.groupby(["gameId", "defensiveTeam"]).ngroups
    L += ["## 2. Cobertura y frecuencia de alertas",
          f"- Jugador‑partidos con intervenciones observadas: {len(allpg)}; con ≥{CFG.min_game_obs} comparables: {len(cases)} ({len(cases) / len(allpg):.0%}).",
          f"- Evaluables (referencia suficiente en algún punto): «en ese momento» {ev_l} ({ev_l / len(cases):.0%} de los anteriores); retrospectivo {ev_r} ({ev_r / len(cases):.0%}). "
          f"Sin evidencia suficiente: {1 - ev_l / len(cases):.0%} / {1 - ev_r / len(cases):.0%}.",
          f"- Jugador‑partidos con al menos una marca: en ese momento {nflag_l} ({nflag_l / max(ev_l, 1):.1%} de los evaluables); retrospectivo {nflag_r} ({nflag_r / max(ev_r, 1):.1%}); en ambos modos {both}.",
          f"- Marcas por equipo‑partido (en ese momento): {nflag_l / teamgames:.2f} en promedio ({teamgames} equipo‑partidos).", "",
          "## 3. Sensibilidad a parámetros (jugador‑partidos con marca, modo «en ese momento»)", "| Variante | Con marca | Δ vs base |", "|---|---|---|"]
    variants = [("Base", {}), ("Umbral 10 pts", {"drop_pct": 10.0}), ("Umbral 20 pts", {"drop_pct": 20.0}), ("Persistencia 2", {"persistence": 2}), ("Persistencia 4", {"persistence": 4}),
                ("Multiplicador de variabilidad 1.0", {"habit_mult": 1.0}), ("Multiplicador 2.0", {"habit_mult": 2.0}), ("Referencia mín. 8", {"min_ref_n": 8}), ("Referencia mín. 20", {"min_ref_n": 20})]
    for name, kw in variants:
        r = live if not kw else run(df, dataclasses.replace(CFG, **kw), "live", cases)
        n = sum(v["flag"] for v in r.values())
        L.append(f"| {name} | {n} | {n - nflag_l:+d} |")
    base = baseline(df, cases)
    nb = sum(v["flag"] for v in base.values())
    inter = sum(base[k]["flag"] and live[k]["flag"] for k in cases)
    union = sum(base[k]["flag"] or live[k]["flag"] for k in cases)
    bpa = sum(v["pa"] for v in base.values() if v["flag"])
    L += ["", "## 4. Comparación con un baseline simple",
          "Baseline: referencia = media de todas sus jugadas válidas previas (sin separar alineación, sin excluir play action, sin escalar por variabilidad); marca si las últimas 3 jugadas están <85% de esa referencia (≥10 previas).",
          f"- Baseline con marca: {nb} ({nb / len(cases):.1%} de los casos) vs SnapReverse {nflag_l} ({nflag_l / len(cases):.1%}). Coinciden en {inter}; unión {union} (Jaccard {inter / max(union, 1):.2f}).",
          f"- De las marcas del baseline, {bpa} ({bpa / max(nb, 1):.0%}) incluyen al menos una jugada de play action, contexto que SnapReverse excluye. Esto muestra qué contexto cambia la lista, **no** cuál es «mejor».", ""]
    # estabilidad posterior (exploratorio)
    nxt = []
    for k, v in live.items():
        pts = [p for p in v["pts"] if p["evaluated"]]
        idx = next((i for i, p in enumerate(pts) if p["status"] == STATUS_FLAG), None)
        if idx is not None and idx + 3 < len(pts) + 0:
            nxt.append(np.mean([p["index"] for p in pts[idx + 1: idx + 4]]))
    L += ["## 5. Qué pasa después de una marca (exploratorio)",
          f"- Primeras marcas con ≥3 intervenciones posteriores: {len(nxt)}; índice medio de las 3 siguientes: {np.mean(nxt):.0f} (mediana {np.median(nxt):.0f})." if nxt else "- Muestra insuficiente.",
          "- Un valor cercano a 100 es compatible con **regresión a la media** o con cambios de contexto; no demuestra que la marca fuera falsa ni verdadera. Sin placebo ni etiquetas no se interpreta causalmente.", "",
          "## 6. Qué falta para validar de verdad",
          "Etiquetas de entrenadores sobre qué secuencias merecían revisión (con su origen documentado), participación verificada y partidos fuera de estas semanas (1–8, 2021) para una evaluación cronológica fuera de muestra."]
    Path(__file__).resolve().parent.parent.joinpath("VALIDACION.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
