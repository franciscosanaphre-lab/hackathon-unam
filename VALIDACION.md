# Validación exploratoria de SnapReverse

> **No hay etiquetas humanas ni ground truth** (nadie marcó qué secuencias «merecían» revisión). Por eso **no se reporta precisión, recall ni «detección correcta»**. Lo siguiente describe comportamiento del método: cobertura, frecuencia de alertas, estabilidad ante parámetros y comparación con un baseline. Todo es **exploratorio** y no prueba utilidad deportiva ni causalidad.

## 1. Corrección (pruebas automáticas)
Ver `backend/tests/`: conversión frame↔tiempo, ventana 0–1 s, ausencia de información futura, referencia/índice, emparejamiento y muestras insuficientes.

## 2. Cobertura y frecuencia de alertas
- Jugador‑partidos con intervenciones observadas: 3238; con ≥3 comparables: 2211 (68%).
- Evaluables (referencia suficiente en algún punto): «en ese momento» 1457 (66% de los anteriores); retrospectivo 1992 (90%). Sin evidencia suficiente: 34% / 10%.
- Jugador‑partidos con al menos una marca: en ese momento 56 (3.8% de los evaluables); retrospectivo 30 (1.5%); en ambos modos 26.
- Marcas por equipo‑partido (en ese momento): 0.23 en promedio (244 equipo‑partidos).

## 3. Sensibilidad a parámetros (jugador‑partidos con marca, modo «en ese momento»)
| Variante | Con marca | Δ vs base |
|---|---|---|
| Base | 56 | +0 |
| Umbral 10 pts | 56 | +0 |
| Umbral 20 pts | 52 | -4 |
| Persistencia 2 | 184 | +128 |
| Persistencia 4 | 17 | -39 |
| Multiplicador de variabilidad 1.0 | 158 | +102 |
| Multiplicador 2.0 | 19 | -37 |
| Referencia mín. 8 | 64 | +8 |
| Referencia mín. 20 | 42 | -14 |

## 4. Comparación con un baseline simple
Baseline: referencia = media de todas sus jugadas válidas previas (sin separar alineación, sin excluir play action, sin escalar por variabilidad); marca si las últimas 3 jugadas están <85% de esa referencia (≥10 previas).
- Baseline con marca: 486 (22.0% de los casos) vs SnapReverse 56 (2.5%). Coinciden en 50; unión 492 (Jaccard 0.10).
- De las marcas del baseline, 374 (77%) incluyen al menos una jugada de play action, contexto que SnapReverse excluye. Esto muestra qué contexto cambia la lista, **no** cuál es «mejor».

## 5. Qué pasa después de una marca (exploratorio)
- Primeras marcas con ≥3 intervenciones posteriores: 47; índice medio de las 3 siguientes: 85 (mediana 87).
- Un valor cercano a 100 es compatible con **regresión a la media** o con cambios de contexto; no demuestra que la marca fuera falsa ni verdadera. Sin placebo ni etiquetas no se interpreta causalmente.

## 6. Qué falta para validar de verdad
Etiquetas de entrenadores sobre qué secuencias merecían revisión (con su origen documentado), participación verificada y partidos fuera de estas semanas (1–8, 2021) para una evaluación cronológica fuera de muestra.