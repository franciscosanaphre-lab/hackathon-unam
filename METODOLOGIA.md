# Metodología — SnapReverse: Índice de Explosividad Relativa

## Procedencia y qué permiten los datos
- `data/` (solo lectura): `games`, `plays`, `players`, `pffScoutingData` y 122 archivos `tracking/` (temporada **2021**, semanas 1–8, 10 fps, columnas x, y, s, a, o, dir, event). Es el formato del Big Data Bowl; **no** se verificó que coincida con el tracking 2023 del sitio del reto (no se accedió a la web) y no se sustituyó por otra fuente.
- Solo jugadas de pase con dropback. `ball_snap` (o `autoevent_ballsnap`) existe en 8,533 de 8,557 jugadas; el tracking empieza ≈0.5 s antes del snap y 99.7% de las jugadas tiene ≥1.5 s posteriores. Por eso **sí** se mide el arranque desde el snap.
- Claves: `(gameId, playId)` único en plays; `(gameId, playId, nflId)` único en pff. Las uniones se validan sin multiplicar filas. El balón (`nflId` vacío) se trata aparte.
- **Participación individual NO verificada.** No se consultó nflverse (sin acceso verificado en esta sesión). Por tanto se habla de «intervenciones observadas» (Pass Rush en jugadas de pase con tracking), no de snaps totales; no hay carga acumulada, ni descanso, ni sugerencia de rotación. Los intervalos sin observación no son descanso.

## Métrica
- Ventana: muestras originales en snap+1 … snap+10 (1.0 s). Sin interpolación.
- `v` = media de la rapidez `s` (yd/s, del proveedor) en esa ventana.
- **Índice = 100 · v / v_ref**, con `v_ref` = mediana propia del defensivo. 100 = su referencia; 80 = 80% de *esa medida*, no de capacidad fisiológica. No se trunca a 0–100.
- Un solo componente: rapidez y desplazamiento a 1 s correlacionan 0.988, usar ambos duplicaría la misma señal. No se usa aceleración máxima (ruidosa y aislada).
- Referencia: intervenciones comparables del mismo grupo de alineación (Interior, Borde, Borde OLB, Otra) si hay ≥8 en ≥2 partidos; si no, todas las suyas. Válida solo con n ≥ 12, ≥ 2 partidos y `v_ref` ≥ 0.8 yd/s (sin divisiones cerca de cero).
- Exclusiones: ventana incompleta, rapidez faltante, jugada terminada (lanzamiento, sack, carrera) antes de 1 s, sin snap. **Play action** se grafica pero queda fuera de referencia y alertas (rapidez mediana 1.59 vs 2.12 yd/s: otro contexto).
- Contexto mostrado (no se ajusta con modelos): alineación, down y distancia, formación, cobertura, rushers, bloqueadores asignados, tiempo hasta lanzamiento/sack.

## Suavizado e incertidumbre
Media móvil de 3 intervenciones comparables; banda = ±1.96·EE de esa ventana (n pequeño: orientativa). Modo *en ese momento* usa ventana solo pasada; retrospectivo, centrada. La «variación habitual» es 1.4826·MAD/mediana de la referencia.

## Reglas de revisión (heurísticas configurables en `backend/snapreverse/config.py`, no médicas)
- *Caída observada para revisar*: las últimas 3 intervenciones comparables del partido están todas por debajo de `100 − T`, con `T = max(15, 1.5 × variación habitual)`.
- *Evidencia insuficiente*: referencia sin n/partidos/valor mínimo, o < 3 intervenciones comparables en el partido.
- Si no, *dentro de su variación habitual*.
- **En ese momento**: referencia y hábito calculados solo con intervenciones estrictamente anteriores (hay prueba que lo verifica). **Retrospectivo**: toda la evidencia del jugador.

## Sensibilidad (resultado real)
Sobre 1,914 jugador‑partidos con ≥6 intervenciones: «en ese momento» 6 con marca / 1,323 estables / 585 evidencia insuficiente; retrospectivo 2 / 1,763 / 149. Las marcas son raras y poco estables entre modos. En el caso demo, la única marca «en ese momento» desaparece en modo retrospectivo. El endpoint `/sensitivity` muestra cómo cambia la mediana del índice con otras decisiones (media vs mediana, solo otros partidos, incluir play action, desplazamiento).

## Límites
No mide energía, fatiga ni lesiones; no sabe si una sustitución mejora el resultado; no es ranking de talento. Menor movimiento puede ser contención, stunt, cobertura, doble bloqueo o liberación rápida. Muestras pequeñas por partido (mediana 8 intervenciones). Sin validar contra resultados.
