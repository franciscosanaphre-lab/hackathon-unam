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

## Estados y referencias: qué significa cada cifra
- **Estado de la jugada**: regla aplicada hasta esa intervención. **Estado al final del partido**: la regla en el último punto. **Resumen del partido**: índice mediano, muestra y marcas. Pueden diferir (una secuencia baja a mitad de partido no cambia el estado final si las últimas jugadas volvieron a su rango).
- **Referencia**: en «en ese momento» es **creciente** (solo intervenciones previas a cada punto; las tarjetas muestran la del último punto); en «retrospectivo» es **fija**. Por eso la tabla de sensibilidad (base retrospectiva, grupo de alineación de cada jugada) y las tarjetas del modo «en ese momento» pueden diferir legítimamente (p. ej. 2.59 vs 2.72 yd/s). En retrospectivo, la base de sensibilidad coincide exactamente con la tarjeta (hay prueba).
- Una intervención se **evalúa** solo si es comparable (sin play action, ventana válida) y tiene referencia suficiente; las marcas solo cuentan sobre intervenciones evaluadas.

## Emparejamiento de la jugada de referencia
Filtros duros: mismo jugador, comparable, mismo grupo de alineación; en «en ese momento» solo jugadas anteriores. Se elige la de **menor puntaje de diferencias de contexto** (alineación exacta y bloqueadores asignados pesan 2; rushers, down, distancia, formación, tipo de cobertura y tiempo hasta lanzamiento pesan 1); empate: otro partido (historial), luego cercanía cronológica. **No se usa la rapidez** (hay prueba). Calidad: alta (peso de diferencias ≤1), media (2–3), baja (≥4). Si no hay jugadas previas comparables se informa y se conserva el replay de la jugada seleccionada. No existe asignación (stunt, contención) en los datos: no se infiere.

## Métricas complementarias evaluadas (no incorporadas a la UI)
Con 3,795 intervenciones de 12 partidos: tiempo de reacción (primer frame >1 yd/s) correlaciona −0.77 con la rapidez; rapidez 0–0.5 s, 0.5–1 s y avance longitudinal 0.89–0.96; **desplazamiento lateral 0.26** (casi independiente), pero depende de la asignación/carril (contención, stunt) que los datos no traen, por lo que no es defendible como «explosividad». Se descartó añadirlas: redundantes o no interpretables. El avance hacia el QB requiere identificar al QB y su dropback; queda como trabajo futuro.

## Validación
Ver `VALIDACION.md` (`.venv/bin/python -m backend.validation`): cobertura, alertas por partido/jugador, evidencia insuficiente, sensibilidad a parámetros y baseline simple. **Sin etiquetas humanas no se reporta precisión ni recall.** Resultados: marcas en 56 de 1,457 jugador‑partidos evaluables «en ese momento» (3.8%) y 30 de 1,992 en retrospectivo (1.5%); muy sensible a la persistencia (2 jugadas: 184; 4: 17) y al multiplicador de variabilidad (1.0: 158; 2.0: 19): los umbrales son heurísticos. El baseline simple marca 22% de los casos y 77% de sus marcas incluyen play action.

## Límites
No mide energía, fatiga ni lesiones; no sabe si una sustitución mejora el resultado; no es ranking de talento. Menor movimiento puede ser contención, stunt, cobertura, doble bloqueo o liberación rápida. Muestras pequeñas por partido (mediana 8 intervenciones). Sin validar contra resultados.
