# Guion de demo (90 s) — funcionalidades reales

Casos calculados por el backend con criterios explícitos (`/api/demo-cases`); la app carga el caso «señal» al abrir y todo se reinicia con «↺ Reiniciar».
- **Señal** (por defecto): Shaquil Barrett (TB), semana 8, TB @ NO, `gameId=2021103111`, `nflId=41915`, jugada `231` (Q1 13:06). Criterio: marca en ambos modos, mayor persistencia mínima.
- **Variación normal**: Montez Sweat (WAS), semana 2, `gameId=2021091600`, `nflId=47809`.
- **Contexto**: Khalil Mack (CHI), semana 3, `gameId=2021092601`, `nflId=41231`, jugada `144`: la referencia difiere en alineación, bloqueadores y rushers.

1. **Problema (10 s).** «Un entrenador de línea defensiva no puede ver todas las jugadas de pass rush. ¿Cuáles revisar primero?» Mostrar el subtítulo de la app: lista explicable de secuencias, comparando a cada jugador con su historial en contextos similares.
2. **Caso (15 s).** La bandeja de revisión del equipo lista secuencias que cumplen la regla (▲) y las cercanas al umbral, con persistencia, índice medio y muestra. Abrir la de Barrett.
3. **Evidencia (20 s).** «Hallazgo en un minuto»: qué cambió (índice 56, 1.69 yd/s vs 2.99), persistencia (3 jugadas seguidas bajo el umbral), referencia (n=154, 8 partidos). Mostrar la gráfica: triángulo ámbar, tendencia con incertidumbre, franja de variación habitual.
4. **Comparación contextual (20 s).** Replay sincronizado al snap con una jugada de referencia elegida por contexto (calidad ALTA; difiere solo el tipo de cobertura). Avanzar frames (+0.1 s cada uno), ventana de la métrica 0–1 s resaltada.
5. **Acción de revisión (10 s).** Explicar diferencias con IA / chat; exportar el reporte (.md). Recalcar: «caída de rapidez ≠ fatiga ni lesión».
6. **Validación y límites (15 s).** Cambiar a «Retrospectivo»: algunas secuencias no se repiten (la bandeja lo indica). VALIDACION.md: marcas raras (3.8%), muy sensibles a umbrales, **sin etiquetas humanas no hay precisión/recall**. Participación y descanso no verificados.

*No se inventan criterios del concurso: el reto pide código Python, visualización/herramienta y README de 3–5 oraciones, que se cumplen.*
