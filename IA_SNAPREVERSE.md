# SnapReverse AI — Coach Intelligence

Copiloto analítico sobre el motor de métricas existente. **Python calcula; Nova interpreta.** El dashboard funciona sin IA.

## Arquitectura
Entrenador → React (`AIPanel`, `ChatDrawer`, botón en `Compare`) → `POST /api/ai/*` → agente (`backend/snapreverse/ai/agent.py`) → Amazon Nova vía Bedrock **Converse API** (`bedrock.py`) ↔ herramientas Python de solo lectura (`tools.py`) → métricas/tracking existentes.
- El navegador solo envía identificadores (`nflId`, `gameId`, `playId`); el backend resuelve los datos.
- Bedrock se llama solo desde el backend. Cliente: `boto3.client("bedrock-runtime", region_name=...)`; credenciales por la cadena estándar de boto3.
- **Modelo**: `BEDROCK_MODEL_ID` (por defecto en `.env.example`: `us.amazon.nova-2-lite-v1:0`, verificado con llamada real; si falta la variable el código usa `us.amazon.nova-pro-v1:0`, como piden las reglas del hosting). Región `AWS_REGION` (us-east-1).

## Herramientas (lista cerrada, parámetros validados, contexto fijado al jugador/partido)
| Herramienta | Qué devuelve |
|---|---|
| `get_player_performance` | índice, referencia, variabilidad, muestra, calidad, límites |
| `investigate_performance_change` | ambos modos (en ese momento / retrospectivo), mitades con bootstrap 95%, veredicto: estable / marca no robusta / persistente / insuficiente |
| `compare_interventions` | rapidez, desplazamiento, aceleración robusta (mediana Δs/Δt), diferencias de contexto |
| `find_relevant_plays` | jugadas por criterio fijo (menor/mayor índice, primera marca, cercanas a referencia, contraste) con la regla declarada |
| `evaluate_available_alternatives` | alineaciones observadas del jugador y compañeros del mismo grupo, con n y confusores; no ordena por «mejor» |

Cada resultado crea **tarjetas de evidencia** (E1, E2…) construidas por Python. Máx. 6 llamadas a herramientas por petición.

## Verificación de respuestas
IDs E# y `playId` que el modelo cite se filtran contra los devueltos por las herramientas. Cada cifra del texto se contrasta con los números de las herramientas; si no coincide, la UI muestra «cifras sin verificar». Esto detecta cifras inventadas, **no** errores de interpretación (p. ej. confundir índice con referencia): lee siempre las tarjetas.

## Endpoints
`GET /api/ai/status` · `POST /api/ai/analyze-player` · `POST /api/ai/chat` · `POST /api/ai/compare-plays`. Errores AWS → 503/429 con `ai_available:false`; el resto de la app sigue funcionando.

## Configurar AWS sin exponer llaves
1. `cp .env.example .env` y pega las llaves temporales (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`). `.env` está en `.gitignore` y no va en el zip de entrega.
2. Reinicia el backend. Si aparece «credenciales expiraron», actualiza `.env` y reinicia.
3. Las llaves que se pegaron en un chat deben considerarse expuestas: **rótalas** al terminar el evento.

## Límites de costo/seguridad
Temperatura 0.2, salida ≤1,500–1,800 tokens, historial ≤6 turnos, mensajes ≤800 caracteres, presupuesto `AI_MAX_CALLS`, `AI_CALLS_PER_MINUTE`, concurrencia 2, timeouts, caché de 32 informes. Nunca se envía tracking crudo. No hay llamadas automáticas al cambiar selectores ni por frame.

## Probar
```bash
.venv/bin/uvicorn backend.main:app --port 8000          # abre http://localhost:8000
curl -s -X POST localhost:8000/api/ai/chat -H 'content-type: application/json' -d '{"nflId":43298,"gameId":2021092611,"mode":"live","message":"¿Qué debería revisar el entrenador?"}'
.venv/bin/python -m pytest backend/tests -q               # incluye pruebas de IA con Bedrock simulado
```

## Limitaciones
Sin participación verificada ni llamadas tácticas/asignaciones: no se afirma la «mejor táctica» ni se sugiere rotar. El modelo puede redactar mal una interpretación aunque las cifras sean correctas. Las respuestas del chat son texto libre; las tarjetas son la fuente verificable.

## Demo (60–90 s)
1. Cargar caso demo (Leonard Floyd, TB @ LA, `gameId=2021092611`). 2. «Analizar con IA»: hallazgo real (rendimiento estable; la única marca de la jugada 2842 no es robusta). 3. En una tarjeta de jugada, «Ver replay» abre el comparador. 4. «Explicar diferencias con IA». 5. Chat: «¿Qué debería revisar el entrenador?» y «¿Qué táctica garantiza más sacks?» → responde que no hay evidencia suficiente.
