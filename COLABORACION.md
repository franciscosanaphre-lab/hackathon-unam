# Colaboración con Git y GitHub

Repositorio privado: pendiente de autenticación y creación en GitHub. Rama compartida: `main`.
Cada persona usa su propia cuenta GitHub y su propia copia del repositorio. El colaborador debe aceptar la invitación antes de clonar.

## Preparar otra computadora Windows (CMD)

Instala Git para Windows y GitHub CLI desde sus sitios oficiales. Abre una nueva ventana CMD y ejecuta:

```cmd
git --version
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
git config --global user.name "TU NOMBRE"
git config --global user.email "TU CORREO DE GITHUB"
```

Cuando el repositorio esté creado, usa su URL HTTPS real:

```cmd
cd /d "%USERPROFILE%\Documents"
git clone URL_HTTPS_DEL_REPOSITORIO hackathon-unam
cd hackathon-unam
git switch main
git config --local pull.ff only
git config --local push.default simple
.hackathon\setup.cmd
.hackathon\setup.cmd --check
```

El instalador reconoce `.hackathon/proyecto` y prepara esta copia existente. Descarga Python 3.12.12, uv 0.11.19, Node 22.23.1, npm 10.x e instala las dependencias fijadas en `.hackathon/requirements.lock` y `dashboard/package-lock.json`. No cambies sus versiones. Conserva `.hackathon` y `.kiro`.

Para crear la configuración local sin sobrescribirla:

```cmd
if not exist .env copy .env.example .env
if not exist data mkdir data
```

Las credenciales se introducen solo en `.env`; nunca se comparten por Git. `data` estaba vacío al configurar Git: Git no versiona carpetas vacías. Antes de agregar datos, comprueba sus permisos de distribución, información personal y tamaño. No subas archivos de 50 MiB o más sin acordar una estrategia; GitHub rechaza archivos mayores de 100 MiB.

## Ejecutar el proyecto

Backend FastAPI (desde la raíz):

```cmd
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Dashboard React, Vite, TypeScript y Tailwind, en otra ventana CMD desde la raíz:

```cmd
set "PATH=%CD%\.hackathon\.tools\node;%PATH%"
cd dashboard
npm run dev
```

Abre la dirección localhost que indique Vite. Backend: http://localhost:8000/health.
Después de cambios en dependencias autorizados por el equipo, ejecuta de nuevo `.hackathon\setup.cmd` desde la raíz.

## Rutina diaria

Antes de editar, desde la raíz:

```cmd
git status
git switch main
git pull --ff-only origin main
```

Si hay cambios locales, guárdalos en un commit revisado antes de integrar trabajo remoto. No cambies de rama con trabajo pendiente sin revisarlo.
Después de editar (sustituye las rutas por tus archivos reales):

```cmd
git diff
git add backend/main.py dashboard/src/App.tsx
git diff --cached
git commit -m "Describe el cambio realizado"
git pull --ff-only origin main
git push origin main
```

Agrega solo archivos revisados. No publiques `.env`, `.venv`, `node_modules`, herramientas descargadas, cachés, registros ni credenciales. `.env.example` debe conservar únicamente valores vacíos o ejemplos sin secretos. Si push se rechaza porque el otro publicó cambios, descarga e integra esos cambios; nunca fuerces el push.

## Conflictos o historiales divergentes

Si `pull --ff-only` avisa de divergencia y tus cambios están guardados en commits:

```cmd
git fetch origin
git merge origin/main
```

Si aparece un conflicto, ejecuta `git status`, abre cada archivo indicado y acuerda con tu compañero el contenido correcto. Resuelve los bloques `<<<<<<<`, `=======`, `>>>>>>>` conservando el trabajo necesario de ambos y quitando los marcadores. No aceptes todo un lado sin revisar.

```cmd
git add RUTA_DEL_ARCHIVO_RESUELTO
git diff --cached
git commit
git push origin main
```

Prueba la aplicación antes de publicar. Para cancelar una integración en conflicto iniciada con el árbol limpio, puedes usar `git merge --abort`. No uses `git reset --hard`, no borres historiales y no uses `git push --force`.

## Trabajar con Codex

Antes de iniciar una tarea, descarga cambios y revisa `git status`. Indica a Codex qué archivos puede editar, pide que inspeccione cambios existentes y que conserve modificaciones ajenas. Coordinen tareas sobre archivos distintos; si ambos necesitan el mismo archivo, acuerden turnos. Revisa el diff antes de cada commit. No permitas que Codex descarte archivos, fuerce publicaciones o reescriba historial para resolver un conflicto. Mantén todos los cambios dentro del stack del evento. No hay sincronización automática configurada.

## Verificar sincronización

```cmd
git fetch origin
git status -sb
git rev-list --left-right --count HEAD...origin/main
git remote -v
git branch --show-current
```

El conteo `0 0` indica commits sincronizados; además `git status` debe mostrar el árbol limpio y la rama debe ser `main`. Los archivos ignorados permanecen locales y no se sincronizan. La privacidad y los colaboradores se consultan en Settings del repositorio; la invitación debe aceptarse desde la cuenta del amigo.
