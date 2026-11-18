# Instrucciones

Requisitos: el proyecto ya trae `.venv/` (Python 3.12) y `.hackathon/.tools/node` (Node 22). Verifica con `sh .hackathon/setup.sh --check` (Windows: `.\.hackathon\setup.cmd --check`). Los datos van en `data/` (solo lectura). No requiere internet.

## Windows (PowerShell, desde la raíz del proyecto)
```powershell
# Backend (carga y calcula métricas al arrancar, ~10 s)
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000

# Frontend en desarrollo (otra terminal)
cd dashboard
npm install        # solo la primera vez (versiones fijadas en package.json)
npm run dev        # http://localhost:5173 con proxy de /api a :8000

# Build de producción (el backend sirve dashboard/dist en http://localhost:8000)
npm run build
```
Si `npm` no está en el PATH: `$env:Path = "$PWD\.hackathon\.tools\node;$env:Path"` (en macOS/Linux: `export PATH="$PWD/.hackathon/.tools/node/bin:$PATH"`).

## macOS / Linux
```bash
.venv/bin/uvicorn backend.main:app --port 8000
cd dashboard && npm run dev
```

## Pruebas
```bash
.venv/bin/python -m pytest backend/tests -q      # Windows: .\.venv\Scripts\python.exe -m pytest backend\tests -q
cd dashboard && npm run build                     # tsc --noEmit + vite build
```

## Endpoints principales
`GET /health` · `/api/status` · `/api/config` · `/api/demo-case` · `/api/games` · `/api/games/{gameId}/teams/{team}/players` ·
`/api/players/{nflId}/games/{gameId}/series?mode=live|retro` · `/api/players/{nflId}/games/{gameId}/sensitivity` ·
`/api/replay?gameId&playId&nflId` · `/api/compare?nflId&gameId&playId[&refGameId&refPlayId][&mode]`
