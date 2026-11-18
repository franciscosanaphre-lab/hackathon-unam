# SnapReverse — Índice de Explosividad Relativa

**Un entrenador de línea defensiva no puede ver todas las jugadas de pass rush. SnapReverse le dice cuáles revisar primero y por qué.**
Mide qué tan rápido arranca cada defensivo en el primer segundo tras el snap, lo compara con **su propio historial en contextos similares** y convierte tracking NFL en una lista explicable de secuencias que vale la pena ver en video, con replays sincronizados al snap. Está pensado para entrenadores de línea defensiva y como apoyo para analistas y comentaristas. Es honesto a propósito: casi siempre dice «normal» o «no hay evidencia suficiente», y cuando marca algo muestra la evidencia, el contexto y las explicaciones alternativas. No mide fatiga, energía ni lesiones, ni predice si una rotación mejora el resultado.

> Stack: Python (FastAPI, pandas, NumPy) · React + Vite + TypeScript · Amazon Nova (opcional, vía Bedrock).

---

## 1. Qué encontramos

**Datos reales:** tracking NFL 2021 (semanas 1–8): 122 partidos, 36,263 intervenciones de pass rush de 698 jugadores. El snap está presente en 99.7% de las jugadas, así que sí podemos medir el arranque desde el snap.

1. **Las caídas persistentes de explosividad son raras.** Con la regla base (3 intervenciones seguidas bajo el umbral), solo **56 de 1,457** jugador‑partidos evaluables (3.8%) reciben alguna marca «en ese momento» y **30 de 1,992** (1.5%) en modo retrospectivo. En la mayoría de los casos la respuesta correcta es «dentro de su variación habitual» o «evidencia insuficiente».
2. **Las marcas son frágiles.** Cambian mucho con los parámetros: exigir 2 jugadas seguidas da 184 marcas; exigir 4, solo 17. Y varias marcas «en ese momento» desaparecen al usar toda la historia del jugador (solo 26 aparecen en ambos modos). Por eso la app las presenta como «secuencia para revisar», nunca como conclusión.
3. **El contexto cambia la lectura.** Con play action la salida es mucho más lenta (mediana 1.59 vs 2.12 yd/s); un criterio ingenuo que lo ignora marcaría 22% de los casos y 77% de esas marcas involucran play action. Por eso comparamos solo jugadas del mismo contexto y mostramos qué difiere.
4. **No vimos una caída general con el paso de las jugadas.** La rapidez mediana de salida se mantiene estable a lo largo de las intervenciones de un partido (exploración sobre todos los jugadores, sin control de contexto); el patrón «se cansa al final» no aparece como tendencia poblacional en estos datos.
5. **Ejemplo real:** Shaquil Barrett (TB, semana 8): una secuencia de 3 jugadas con índice medio 43 respecto a su referencia, **en el primer cuarto**. Es una señal digna de revisar en video, pero a esa altura del partido no es compatible con «desgaste»: justo el tipo de matiz que la herramienta hace visible.

**Lo que no concluimos:** fatiga, lesión, capacidad restante ni necesidad de sustitución. Participación y descanso reales no están verificados, así que hablamos de «intervenciones observadas», no de snaps totales.

## 2. Cómo lo sabemos

- **Métrica transparente:** `índice = 100 × rapidez media 0–1.0 s tras el snap ÷ mediana propia del jugador`. 100 = su referencia (no es «% de energía»). Una sola medida: rapidez y desplazamiento a 1 s correlacionan 0.99, así que usar ambas duplicaría la señal. Se descartaron otras (reacción, avance, desplazamiento lateral) por redundantes o dependientes de la asignación, que los datos no traen.
- **Comparación justa:** referencia propia por grupo de alineación; play action y ventanas incompletas quedan fuera; la jugada de referencia se elige por **contexto** (bloqueadores, alineación, down, distancia, formación, cobertura) y **nunca por su rapidez**; la calidad de la comparación (alta/media/baja) sigue reglas explícitas.
- **Sin información futura:** el modo «En ese momento» usa solo intervenciones anteriores (referencia, umbral, suavizado y comparación automática). El modo «Retrospectivo» está identificado como tal.
- **Reglas deterministas y configurables:** una caída exige persistencia (3 seguidas) y muestra suficiente (referencia ≥12 intervenciones en ≥2 partidos). Los umbrales son heurísticos, no límites médicos.
- **Verificación automática:** 33 pruebas (`pytest`) cubren uniones sin multiplicar filas, ventana 0–1 s idéntica a las muestras del replay, 10 fps comprobados con los timestamps reales, ausencia de datos futuros, que el emparejamiento ignore la rapidez, casos con pocos datos y errores de la API.
- **Validación exploratoria:** `VALIDACION.md` reporta cobertura, alertas por partido, evidencia insuficiente, sensibilidad a parámetros y comparación con un baseline simple. **No hay etiquetas humanas, así que no reportamos precisión ni recall**; todo es exploratorio y no prueba utilidad deportiva ni causalidad.
- **IA trazable (opcional):** SnapReverse AI usa Amazon Nova, pero **no calcula nada**: consulta funciones de Python de solo lectura, y cada cifra y jugada que cita se contrasta contra esos resultados (si no coincide, se marca «sin verificar»). La app funciona completa sin IA.

Detalle completo: [`METODOLOGIA.md`](METODOLOGIA.md) · [`VALIDACION.md`](VALIDACION.md) · [`IA_SNAPREVERSE.md`](IA_SNAPREVERSE.md).

## 3. Cómo ejecutarlo

**Requisitos:** los datos en `data/` (`games.csv`, `plays.csv`, `players.csv`, `pffScoutingData.csv` y `tracking/`), no incluidos en el repositorio por tamaño; el entorno (`.venv`, Node) se prepara con `sh .hackathon/setup.sh` (Windows: `.\.hackathon\setup.cmd`). No requiere internet salvo para la IA opcional.

**macOS / Linux**
```bash
.venv/bin/uvicorn backend.main:app --port 8000
```
**Windows (PowerShell)**
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
```
Abre **http://localhost:8000**. El backend tarda ~10 s en calcular las métricas y unos 15 s más en preparar los casos demo (la página espera sola). Se abre el caso «señal»; también hay «variación normal» y «contexto».

**Probar el flujo (60 s):** elige un caso → mira la **bandeja de revisión** → abre una secuencia → lee el **resumen** y la gráfica → compara los **replays** (avanza frame a frame: cada uno son 0.1 s) → **exporta el reporte** → alterna *En ese momento* / *Retrospectivo* para ver qué tan robusta es la señal.

**IA (opcional):** copia `.env.example` a `.env` y pega tus llaves temporales de AWS (`.env` no se versiona). El modelo se configura con `BEDROCK_MODEL_ID` (`us.amazon.nova-2-lite-v1:0`).

**Desarrollo y pruebas**
```bash
cd dashboard && npm run dev      # http://localhost:5173 con proxy de /api a :8000
cd dashboard && npm run build    # tsc --noEmit + vite build (el backend sirve dashboard/dist)
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m backend.validation   # regenera VALIDACION.md
```
Más comandos y la lista de endpoints: [`INSTRUCCIONES.md`](INSTRUCCIONES.md) · guion de demo de 90 s: [`DEMO.md`](DEMO.md).

## Límites y pendientes
Sin participación individual verificada (nflverse sin consultar) · sin etiquetas humanas para validar la utilidad deportiva · solo semanas 1–8 de 2021 · umbrales heurísticos · no verificamos que estos datos coincidan con el tracking 2023 del sitio del reto.
