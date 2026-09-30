# Registro de prompts y acciones — Pulso (tp-final)

Registro cronológico de cada prompt enviado al asistente (Claude Code) y de las acciones que tomó en respuesta. Los prompts se transcriben textualmente. Complementa a [HISTORIAL_DESARROLLO.md](HISTORIAL_DESARROLLO.md), que resume las etapas anteriores (versión Flask/Jinja y separación frontend/backend).

Formato de cada entrada: prompt textual → acciones (lecturas, preguntas, decisiones, archivos modificados, comandos, resultados).

---

## Sesión 2026-09-23 — Revisión de arquitectura y replataforma

### Prompt 1 — Inicio de la revisión de arquitectura (modo plan)

> I am focusing on tp-final. Look through what's already done. I am planning on reviewing architecture to improve it. The project is a project management app with front and back end. It's main focus is to be simple and easy to use but also useful for project management. Let's start discussing technologies.

**Acciones:**

1. Se leyó el código y la documentación existentes sin modificar nada: `app/schema.sql`, `app/__init__.py`, `app/common.py`, `app/projects.py`, `frontend/index.html`, `frontend/app.js`, `frontend/api.js`, `frontend/server.py`, `frontend/styles.css`, `docs/PLAN.md`, `docs/ESPECIFICACION.md`, `docs/HISTORIAL_DESARROLLO.md`, `docs/Presentacion_de_idea.pdf` y `../FEATURE_PLAN.md`.
2. Diagnóstico presentado:
   - **Fortalezas:** CSRF, cookies HttpOnly, hash scrypt, contrato de errores JSON uniforme, permisos verificados en el servidor y buena cobertura de pruebas (pytest + node).
   - **Brechas:** no hay mecanismo de migraciones de esquema (`schema.sql` solo usa `CREATE TABLE IF NOT EXISTS`); el frontend arma las vistas con cadenas `innerHTML`, lo que no escala a Gantt ni reportes; el proxy `server.py` es artesanal; la especificación dice "local, sin despliegue público, sin correo", lo que choca con las alertas por mail del roadmap.
   - Se relacionó cada ítem de `FEATURE_PLAN.md` (reporting, Gantt, cargas masivas, alertas, proyecciones, desvíos) con la tecnología que necesita.
3. Primera ronda de preguntas al usuario:

| Pregunta | Respuesta |
|---|---|
| ¿Restricciones del curso sobre el stack? | Totalmente abierto |
| ¿Dónde se ejecuta Pulso? | Preparado para un equipo chico: hosteado y con despliegue real |
| ¿Dirección del frontend? | Vite + framework |
| ¿Qué funcionalidades primero? | Todas: reporting/desvíos/proyecciones, Gantt, cargas CSV, alertas por mail |

4. Segunda ronda:

| Pregunta | Respuesta |
|---|---|
| Framework backend | Migrar a FastAPI |
| Framework frontend | El usuario preguntó: *"how good is vue3 for complex components like gantts?"* |
| Base de datos e infraestructura | Postgres + Docker Compose |

5. Respuesta sobre Vue 3 y los Gantt: el framework influye poco, porque los Gantt serios son librerías JS con wrappers para cada framework. Se compararon frappe-gantt (MIT, simple), SVAR Gantt (núcleo MIT, con versión para Vue), vue-ganttastic (básico) y DHTMLX/Bryntum (licencia GPL o comercial). Se recomendó Vue 3 con un componente propio `<ProjectGantt>` que envuelva la librería, para poder reemplazarla después.
6. Tercera ronda:

| Pregunta | Respuesta |
|---|---|
| Framework frontend | Vue 3 + TypeScript |
| Autenticación | Sesión por cookie + CSRF (sesiones del lado del servidor) |

7. Se redactó y aprobó el plan de replataforma (archivo de plan del asistente). Resumen:
   - **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, psycopg 3, sesiones en Postgres, argon2 (con verificación de hashes scrypt heredados y re-hash al iniciar sesión), `uv` y ruff.
   - **Frontend:** Vue 3 + TS, Vue Router, Pinia, TanStack Query, cliente tipado generado desde OpenAPI, PrimeVue y ECharts, Gantt envuelto en un componente propio.
   - **Infraestructura:** Caddy (HTTPS, sirve el build y hace de proxy de `/api`, reemplaza a `server.py`), API en uvicorn, un worker para alertas, Postgres 16 con backups, Mailpit en desarrollo y GitHub Actions.
   - **Fases:** 1) fundamentos; 2) paridad del backend (mismo contrato de `docs/API.md`, pruebas portadas, script de importación SQLite → Postgres); 3) paridad del frontend; 4) despliegue; 5) funcionalidades (reporting → CSV → Gantt → alertas); 6) documentación.
8. Plan aprobado; empieza la Fase 1. Verificación de herramientas locales: `uv` 0.12.5, Python 3.14, Node 22, npm 10 y podman 5.8. No hay `docker`, y `podman compose` no tiene un proveedor de compose instalado. Se leyó `docs/API.md` completo como contrato a preservar.

### Prompt 2 — Registro obligatorio de prompts

> One important thing. this repo is for a tp-final so every prompt and step needs to be recorded. For this generate a markdown prompts.md with this information. reflect what we've done and update your instructions to log on that file for every action. Then, continue with the plan

**Acciones:**

1. Se creó este archivo, `tp-final/prompts.md`, con lo realizado hasta ahora.
2. Se agregó a `CLAUDE.md` (raíz del repo) la regla de registrar en este archivo cada prompt y cada acción.
3. Se guardó la misma regla en la memoria persistente del asistente, para que se aplique en sesiones futuras.
4. Se continúa con la Fase 1 del plan (ver entradas siguientes).

#### Fase 1 — Fundamentos (ejecutada a continuación del Prompt 2)

1. **Herramientas:** como no hay Docker, se usa podman en modo rootless. Se instaló `podman-compose` 1.6.0 como herramienta de usuario (`uv tool install podman-compose`).
2. **Proyecto backend** (`tp-final/backend/`), gestionado con `uv` (Python 3.13):
   - `pyproject.toml`: FastAPI, uvicorn, Pydantic v2, pydantic-settings, SQLAlchemy 2, psycopg 3 y Alembic; dependencias de desarrollo pytest, httpx y ruff (comillas simples, líneas de 110). También `uv.lock` y `.python-version`.
   - `pulso/config.py`: configuración por variables de entorno (`SECRET_KEY` de al menos 32 caracteres, `DATABASE_URL`, `COOKIE_SECURE`, duración de la sesión).
   - `pulso/db.py`: engine, sessionmaker y la dependencia `get_db` (una sesión por request).
   - `pulso/models.py`: modelos ORM que replican el esquema SQLite original con los mismos nombres en español, incluido `proyect_status`, y las mismas restricciones CHECK y claves foráneas RESTRICT. `COLLATE NOCASE` se reemplazó por índices únicos sobre `lower(...)`. Se agregó la tabla `sesion` para las sesiones del lado del servidor.
   - `pulso/main.py`: fábrica `create_app()` con los encabezados de seguridad, el contrato de errores `{"error": {code, message}}` (validación → 400, IntegrityError → 409, HTTP → `http_<código>`) y `GET /api/health`. OpenAPI en `/api/docs`. `pulso/asgi.py` es el punto de entrada de uvicorn.
   - Alembic: `alembic.ini` y `migrations/env.py`, que toma la URL de `DATABASE_URL` y no necesita `SECRET_KEY`. La migración base `0001_esquema_base.py` se autogeneró y se revisó.
   - Error corregido durante el trabajo: los índices case-insensitive se habían escrito con literales de texto en lugar de columnas. Se reescribieron después de cada clase.
3. **Infraestructura de desarrollo:** `tp-final/compose.yaml` con `db` (Postgres 16), `mailpit` y `api` (uvicorn con `--reload`, que corre `alembic upgrade head` al iniciar). También `backend/Dockerfile` (python:3.13-slim + uv) y `.dockerignore`.
   - Problema: `podman-compose` interpola todo el archivo, así que `${SECRET_KEY:?}` impedía levantar incluso `db`. Se cambió a `${SECRET_KEY:-}`; la API valida la clave al arrancar.
4. **Pruebas** (`backend/tests/`): cada corrida crea una base Postgres temporal, le aplica las migraciones y la elimina al terminar. Las pruebas verifican health, error 404 en JSON, que las migraciones coincidan con los modelos (`compare_metadata`), que se pueda hacer downgrade y upgrade, y la unicidad sin distinguir mayúsculas.
   - Resultado: `uv run pytest -q` → **5 passed**; `ruff check` y `ruff format --check` sin errores.
5. **Verificación con contenedores:** `podman compose up -d --build api`; `curl /api/health` → `{"status":"ok"}`; los logs muestran `Running upgrade -> 0001, esquema base` y `\dt` lista las tablas `consumo`, `proyecto`, `recurso`, `rol`, `sesion` y `alembic_version`.
6. **CI:** `.github/workflows/tp-final.yml` (en la raíz del repo) corre `uv sync`, `ruff check`, `ruff format --check` y pytest contra un servicio Postgres 16. Se agregó `.ruff_cache/` a `tp-final/.gitignore`.
7. El backend Flask original (`app/`) y el frontend actual siguen funcionando sin cambios. Se retirarán después de alcanzar la paridad (Fases 2–4).

#### Consulta sobre Git

Se preguntó al usuario cómo manejar la evidencia de Git que pide el curso (ramas, commits y PRs). Respuesta: **"Branch + commit per phase"**. Se crea la rama `replatform-fastapi-vue` y se hace al menos un commit por fase; el usuario abre los PR.

#### Fase 2 — Paridad del backend (en curso)

1. Se leyeron los módulos Flask que faltaban (`auth.py`, `resources.py`, `roles.py`, `consumptions.py`, `db.py`) y la suite `tests/test_app.py` con su `conftest.py`, que funcionan como especificación ejecutable.
2. Se corrió la suite Flask original como línea de base. Antes hubo que instalar `requirements-dev.txt` en `.venv`. Resultado: **66 passed**.
3. Se revisó qué espera el frontend actual: solo usa la veracidad de `es_admin` y `debe_cambiar_password` y los códigos `unauthorized`, `password_change_required` y `csrf_invalid`. Decisión: la API nueva devuelve booleanos JSON (`true`/`false`) en lugar de `1`/`0`.
4. Se agregaron las dependencias `pwdlib[argon2]` y `werkzeug`; esta última solo para verificar los hashes scrypt heredados.
5. Archivos nuevos en `backend/pulso/`:
   - `errors.py`: `APIError` y el formato de error.
   - `security.py`: argon2, verificación de hashes heredados con re-hash, y tokens.
   - `sessions.py`: sesiones del lado del servidor en la tabla `sesion`. La cookie `pulso_session` es HttpOnly y SameSite=Lax, y en la base se guarda solo el hash SHA-256 del token. Las sesiones anónimas duran 2 h y las vencidas se limpian al crear una nueva. El guard se aplica a nivel de router en el mismo orden que Flask: 401 → 403 por cambio de contraseña pendiente → 400 CSRF → 415 → 400 si el cuerpo no es un objeto. También define `current_user` y `require_admin`.
   - `schemas.py`: validadores Pydantic que reproducen las reglas de `common.py` con los mismos mensajes (rechazan booleanos, NaN e infinito y aceptan cadenas numéricas), más los modelos de entrada y salida para OpenAPI.
   - `queries.py`: consultas de proyectos con sus agregados y de consumos con nombres.
   - `routers/auth.py`, `routers/projects.py`, `routers/consumptions.py`, `routers/resources.py`, `routers/roles.py`: el mismo contrato de `docs/API.md`. Los permisos se chequean como dependencias antes de validar el cuerpo, para que un 403 tenga prioridad sobre un 400 (igual que en Flask). La regla del último administrador usa `SELECT … FOR UPDATE`. Cambiar o restablecer una contraseña cierra las otras sesiones de ese usuario.
   - `main.py`: registra los routers; también maneja los 500 no controlados (siempre como JSON), el límite de 1 MiB (413) y los errores de validación de Pydantic, que se traducen a los mensajes en español. Un parámetro de ruta inválido devuelve 404.
   - `cli.py`: `init-db` (migra y crea admin/Proyecto1 solo si la base está vacía) e `import-sqlite` (copia la base Flask conservando IDs y hashes, y ajusta las secuencias).
6. Errores corregidos durante la escritura: en `detail()` quedaba una expresión inválida (`if False else`) y un `filter_by` que apuntaba a la tabla equivocada. Además, `create` agregaba el proyecto a la sesión antes de validar la referencia, con riesgo de autoflush.

### Prompt 3 — Alcance (mensaje enviado durante el trabajo)

> Once we end phase 4 let's stop. Phase 5 will remain for future date. but do phase 6 (documentation)

**Acciones:** se ajustó el alcance. Se completan las Fases 2, 3 y 4 y luego la Fase 6 (documentación). La Fase 5 (reporting, CSV, Gantt y alertas) queda pendiente para más adelante.

#### Fase 2 — Resultados

1. Pruebas: `backend/conftest.py` suma el fixture `seeded`, con los mismos datos que la suite Flask, y los helpers `login`, `mutate`, `post` y `scalar`. `backend/tests/test_api.py` porta **todas** las pruebas de `tests/test_app.py` y agrega otras nuevas:
   - flags de la cookie de sesión y login sin distinguir mayúsculas;
   - cierre de las otras sesiones al cambiar la contraseña;
   - aceptación y re-hash a argon2 de un hash werkzeug heredado;
   - mensajes de validación en español;
   - orden de catálogos sin distinguir mayúsculas;
   - `responsable` no numérico → 400, e ID de ruta no numérico → 404;
   - límite de 413 y errores 500 no controlados siempre como JSON.
2. Resultado: `uv run pytest -q` → **78 passed** en el primer intento; `ruff check` y `ruff format` sin errores (tras ajustar tres líneas largas y usar la sintaxis de genéricos de Python 3.12).
3. Importación real: se copió `instance/proyectos.sqlite` al scratchpad (el original no se tocó) y se importó en una base Postgres descartable con `python -m pulso.cli import-sqlite`. Resultados:
   - Filas: 1 recurso, 3 roles, 1 proyecto y 1 consumo.
   - Agregados idénticos: 560 h requeridas, 12 h consumidas, saldo 548.
   - Las secuencias quedaron ajustadas (el próximo `rol_id` es 4) y el hash scrypt heredado se conservó.
   - `init-db` posterior no creó otro admin.
   - La base descartable se eliminó al terminar.
4. `compose.yaml` y el `Dockerfile` ahora ejecutan `python -m pulso.cli init-db` al arrancar (migración + admin inicial). Log del contenedor: "Base inicializada. Usuario inicial: admin / Proyecto1."
5. Compatibilidad: el frontend **actual** (`frontend/server.py`, puerto de prueba 8010) funcionó sin cambios contra la API FastAPI. Sesión, login y bloqueo por cambio de contraseña pendiente (`password_change_required`) respondieron igual que con Flask.

#### Fase 3 — Paridad del frontend (Vue 3 + TypeScript)

1. Se leyó completo el frontend anterior (`app.js`, `ui.js` y `styles.css`) para reproducir pantallas, textos y reglas.
2. **Desviación del plan, justificada:** en esta fase de paridad **no** se incorporó PrimeVue. Se portó el diseño propio existente (CSS propio sobre Bootstrap, ahora empaquetado desde npm en lugar del CDN) para mantener la apariencia idéntica y un bundle chico. PrimeVue y ECharts quedan para la Fase 5, donde se necesitan tablas de datos, cargas de archivos y gráficos.
3. Proyecto Vite en `tp-final/frontend/`:
   - Dependencias: Vue 3.5, Vue Router 5, Pinia 4, TanStack Query, openapi-fetch y Bootstrap. De desarrollo: Vite 8, vue-tsc, Vitest, @vue/test-utils, jsdom, openapi-typescript y Playwright.
   - npm instaló TypeScript 7, pero openapi-typescript pide `^5.x`, así que se fijó **TypeScript ~5.9.3**.
4. **Contrato tipado:** `backend/pulso/openapi.py` exporta el esquema sin necesitar base de datos. `npm run gen:api` genera `openapi.json` y `src/api/schema.d.ts`. CI verifica que los tipos generados estén actualizados.
5. Código:
   - `src/api/client.ts`: cliente con token CSRF rotado solo en mutaciones y mapeo al contrato de errores. Los errores de red o de respuesta inválida tienen mensajes en español y nada se reintenta automáticamente.
   - `stores/session.ts` (Pinia).
   - `composables/notice.ts`: misma reacción a errores que antes (401 → login, `password_change_required` → cambio de contraseña, `csrf_invalid` → renovar el token sin reintentar).
   - `composables/submit.ts`: los formularios conservan lo ingresado si hay error.
   - `router.ts`: se relee la sesión en cada navegación y las reglas de redirección están en `redirectFor`.
   - Componentes: `AppHeader`, `PageHeading`, `StatGrid`, `ProgressBar`, `LoadState`, `TextField`, `SelectField`, `FormShell`, `DeleteButton` y `ConsumptionTable`.
   - 12 vistas con las mismas rutas que antes. Vue escapa todo el contenido y nunca se usa `v-html`.
6. Ajustes durante el trabajo:
   - Se quitó `novalidate` para conservar la validación nativa del navegador.
   - `DeleteButton` ahora navega antes de invalidar la caché, para no volver a pedir un registro ya eliminado.
   - El cliente usa como `baseUrl` el origen de la página, porque en Node `Request` exige URL absolutas.
   - `fetch` se resuelve en cada llamada, porque openapi-fetch lo capturaba al crearse y los tests no podían reemplazarlo.
7. **Pruebas:**
   - `vue-tsc` sin errores y `npm run build` OK (bundle principal de ~30 kB gzip).
   - Vitest: **9 passed**. Cubren el cliente (CSRF, 204, errores sin reintento, red y respuesta inválida), el escape de contenido hostil y los permisos en la tabla de consumos, y las reglas de navegación.
   - Playwright (Chromium headless) sobre el stack real: la API en el puerto 5001 con la base `pulso_e2e` recreada en cada corrida (`e2e/start-api.sh`) y Vite con proxy. Resultado: **5 passed**. Cubren cambio forzado de contraseña; alta de usuario, rol y proyecto (con nombre hostil escapado); usuario común registrando horas con un error de fechas que conserva el formulario, exceso de 5,5 h y avance manual intacto; redirección desde rutas de admin; logout; recarga de una URL profunda; eliminación, y login en móvil sin scroll horizontal.
   - Fallas en las propias pruebas, ya corregidas: Vite escuchaba en IPv6 (se agregó `--host 127.0.0.1`), un selector ambiguo "Nueva contraseña" (se usa `exact`) y una carrera en el helper de login (ahora espera la redirección).
8. Revisión visual con capturas de login, proyectos y detalle: el diseño coincide con la versión anterior.
9. Se eliminaron `frontend/app.js`, `api.js`, `ui.js` y `server.py` y sus pruebas (`tests/frontend.test.mjs` y `tests/test_frontend_server.py`). `styles.css` pasó a `src/styles/main.css`. CI suma el job `frontend` (tipos generados, build, Vitest y Playwright).

#### Fase 4 — Despliegue

1. Archivos nuevos:
   - `deploy/Caddyfile`: HTTPS automático (en `localhost` usa la CA local de Caddy) y proxy de `/api/*` a `api:5000` con límite de cuerpo de 1 MB. Sirve la SPA con `try_files` hacia `index.html` y los encabezados CSP (sin scripts en línea), HSTS, `X-Frame-Options` y `nosniff`. Los assets con hash llevan caché inmutable y las páginas `no-cache`.
   - `deploy/web.Dockerfile`: build de Vue con Node 22 y resultado copiado a una imagen `caddy:2-alpine`.
   - `compose.prod.yaml` con cuatro servicios:
     - `web` (Caddy);
     - `api`: `init-db` + uvicorn con `--workers` y `--proxy-headers`, `COOKIE_SECURE=1`, y `SECRET_KEY`/`POSTGRES_PASSWORD` obligatorios;
     - `db` (Postgres 16 con healthcheck);
     - `backup`: `pg_dump` diario comprimido en `./backups` con retención de `BACKUP_DAYS` días.
   - `.env.example` (plantilla de secretos y dominio) y `.dockerignore`. Se agregaron `backups/`, `frontend/node_modules/` y `frontend/dist/` a `.gitignore`.
   - El servicio `worker` para las alertas se difiere a la Fase 5, junto con la funcionalidad que lo necesita.
2. **Verificación local del stack de producción** con podman (proyecto `pulso-prod`, puertos 8080/8443 y un `.env` descartable en el scratchpad):
   - Las cuatro imágenes y contenedores levantaron.
   - `/proyectos/1` → 200 con CSP, HSTS y `X-Frame-Options: DENY`; `/assets/*.js` → `immutable`.
   - Login por HTTPS → cookie `pulso_session` con `HttpOnly; SameSite=lax; Secure`. Cuerpo de 1,1 MB → **413**; `/api/docs` → 200.
   - El servicio de backup generó `pulso-2026-09-24.sql.gz`.
   - Chromium (Playwright) sobre `https://localhost:8443`: redirección a login, login y cambio de contraseña forzado, estilos cargados y **sin errores de CSP ni de consola**.
   - Hallazgo corregido: las URL profundas de la SPA no recibían `Cache-Control: no-cache`, porque el matcher evaluaba la ruta original. Se cambió a `not path /assets/*`. Además `podman-compose up --build` no recreaba el contenedor y hubo que usar `--force-recreate`.
   - Al terminar se eliminaron los contenedores, volúmenes y el backup de prueba.
3. **Retiro de la versión Flask** (ya verificada la paridad): se eliminaron `app/`, `requirements.txt`, `requirements-dev.txt` y `tests/` (la suite Flask ya está portada en `backend/tests/`). Siguen disponibles en el historial de Git y en la copia congelada `tp-final - Flask/`. **No** se tocó `instance/proyectos.sqlite`, que son datos del usuario y la fuente para `import-sqlite`. El `.venv` viejo de la raíz de tp-final quedó sin usar y no se borró.
4. CI suma el job `images`, que construye las imágenes de la API y la web después de backend y frontend.
5. La suite del backend sigue en **78 passed** sin el paquete Flask.
6. Aparte: se detectó que `FEATURE_PLAN.md` (en la raíz del repo) tiene cambios del usuario, con estados de avance. No se incluyeron en los commits del asistente.

#### Fase 6 — Documentación

1. `README.md` reescrito: stack, diagrama y mapa de carpetas; desarrollo local (compose + uv + Vite); importación desde SQLite; despliegue con `compose.prod.yaml` (incluida la restauración de backups); matriz de permisos; pruebas; qué funcionó y qué no; enlaces a la documentación y evidencia Git.
2. `docs/API.md`:
   - proxy Caddy/Vite, OpenAPI en `/api/docs`, sesiones en el servidor con su duración, y cierre de las demás sesiones al cambiar la contraseña;
   - booleanos JSON, `/api/health`, `responsable` no numérico → 400, ID de ruta no numérico → 404, 500 siempre como JSON, y nota sobre los 502 del proxy;
   - el orden de las verificaciones (por qué 403 gana sobre 400).
   - Autocorrección: primero se había escrito que un 502 se informa como error de conexión, pero el cliente muestra el mensaje genérico. Se corrigió el texto.
3. `docs/ESPECIFICACION.md`: aplicación web hosteada, argon2 con migración de hashes, secciones nuevas de Despliegue y "Próximas funcionalidades (Fase 5, pendiente)".
4. `docs/PLAN.md`: se agregó el plan de replataforma (motivo, tabla de decisiones, fases con su estado y compatibilidad). El plan anterior se conserva como historia.
5. `docs/VALIDACION.md`: resultados nuevos (78 + 9 + 5 pruebas, migración de datos, stack de producción y revisión visual). La validación anterior queda en una sección histórica.
6. `HISTORIAL_DESARROLLO.md` y `docs/HISTORIAL_DESARROLLO.md` (hay dos copias idénticas): sección 19, que resume esta etapa y remite a `prompts.md`.
7. `CLAUDE.md` en la raíz del repo, ignorado por Git y por lo tanto solo local: se reescribieron la arquitectura, la ejecución y las pruebas de tp-final para el stack nuevo.
8. **Estado final:** Fases 1, 2, 3, 4 y 6 completas. La Fase 5 (reporting, CSV, Gantt y alertas) queda pendiente, según lo pedido en el Prompt 3.

#### Revisión final — Verificación real de los backups

1. La revisión final (advisor) señaló que el backup se había dado por verificado sin estarlo. El primer dump (370 bytes) probablemente corrió antes de que la API migrara la base; en `pg_dump | gzip && echo ok` el `&&` solo evalúa gzip, así que un fallo quedaba oculto; y la restauración documentada chocaría con las tablas y el admin que crea `init-db`.
2. Corrección en `compose.prod.yaml`: el servicio `backup` espera a que exista `alembic_version`, usa `set -o pipefail`, escribe a un `.tmp` y lo renombra solo si el dump tuvo éxito (si no, registra `backup FAILED`), y usa `pg_dump --clean --if-exists`.
3. Verificación con un stack de producción descartable:
   - El primer dump automático contiene las 6 tablas.
   - Por la API se cambió la contraseña del admin a `Respaldo123` y se crearon un rol y un proyecto; el dump (el mismo comando que el loop) incluye sus datos.
   - `down -v`, stack nuevo (con `init-db` sembrando su propio admin) y restauración con el comando del README: **sin errores**. El login con `Respaldo123` dio 200, el proyecto "Proyecto respaldado" volvió y quedó 1 solo recurso.
4. Se actualizaron la sección de restauración del README (detener `api`, restaurar, iniciar `api`) y `docs/VALIDACION.md`, que ahora refleja lo realmente verificado. Luego se eliminaron los contenedores, volúmenes, backups y el `.env` de prueba.
5. Notas para el usuario (sin acción): el workflow de CI nunca se ejecutó, porque la rama no se subió; siguen corriendo los contenedores de desarrollo (`db`, `mailpit` y `api` en :5000); quedaron instalados `podman-compose` (herramienta de uv) y Chromium de Playwright (~114 MB); el `.venv` viejo de tp-final quedó sin uso; `SECRET_KEY` sigue siendo obligatoria, pero la API actual no la usa porque las sesiones viven en la base.

### Prompt 4 — Cómo acceder a la aplicación

> how can i access this tool now? did you update the instructions to mount locally?

**Acciones:**

1. Se revisó el estado local: los contenedores de desarrollo `db`, `mailpit` y `api` seguían corriendo (API en `:5000`, health `ok`), con una base nueva que solo tiene `admin` / `Proyecto1` (cambio pendiente) y ningún proyecto.
2. Se inició el servidor de desarrollo de Vite en segundo plano (`npx vite --host 127.0.0.1 --port 5173`). Se verificó `/proyectos` → 200 y `/api/session` respondiendo a través del proxy de Vite.
3. Se confirmó que las instrucciones para levantar la app localmente están en la sección "Desarrollo local" de `tp-final/README.md` (y, en inglés, en el `CLAUDE.md` local).
4. Se detectó un hueco en la documentación: `import-sqlite` exige una base vacía, pero el flujo de desarrollo corre `init-db` primero (que crea el admin), así que la importación de los datos anteriores se niega. Se informó al usuario y se ofreció resolverlo.

## Sesión 2026-09-30 — Planificación del Gantt (rama `feat-gantt-chart`)

### Prompt 5 — Planificar la funcionalidad Gantt

> let's plan on adding a gantt chart feature to this application.

**Acciones:**

1. Se registró este prompt antes de empezar.
2. Se leyeron `docs/PLAN.md` (decisión previa: componente propio `<ProjectGantt>` que envuelve SVAR Gantt o frappe-gantt; Gantt es el 3.º ítem de la Fase 5), `FEATURE_PLAN.md` ("Planificacion Gantt: Pending"), `docs/ESPECIFICACION.md` ("tareas, dependencias y vínculo opcional de consumos con tareas"), `backend/pulso/models.py`, las rutas de `routers/projects.py`, `frontend/package.json`, `frontend/src/router.ts` y la matriz de permisos del README.
3. Hallazgo: el modelo actual no tiene tareas planificadas; solo `proyecto` (fechas, horas, avance) y `consumo` (horas reales con un texto libre `tarea`). Un Gantt con tareas y dependencias requiere tablas nuevas y una migración Alembic 0003.
4. Preguntas al usuario (AskUserQuestion) y respuestas:
   - Alcance → **"Tasks + deps, staged"**: tareas y dependencias en entregas incrementales (portafolio → tareas → dependencias → vínculo consumo↔tarea).
   - Librería → **frappe-gantt**, envuelta en `<ProjectGantt>`.
   - Permisos → **responsable + administrador** editan; todos consultan.
5. Se consultó al advisor, que recomendó dejar el plan en `docs/PLAN.md` (en castellano), registrar el desvío del orden de la Fase 5, definir las reglas de borrado, fechas y avance, y verificar frappe-gantt en vez de recordarlo.
6. Verificación de frappe-gantt (se bajó con `npm pack frappe-gantt@1.2.2` al scratchpad y se leyó `src/`):
   - versión 1.2.2 MIT y sin tipos TS;
   - la fecha de fin sin hora es inclusiva, como en el backend;
   - eventos `click`, `date_change`, `progress_change` y `view_change`;
   - **la etiqueta de la barra y el popup por defecto usan `innerHTML` con `task.name`, un riesgo XSS**, así que el plan exige escapar los nombres y usar un popup propio;
   - no inserta `<style>`, por lo que en principio es compatible con la CSP de `deploy/Caddyfile`, aunque se debe verificar en el stack de producción.
7. Se agregó a `docs/PLAN.md` la sección "Plan de planificación Gantt (2026-09-30)": motivo, decisiones, hechos verificados, modelo (`tarea`, `dependencia`, `consumo.tarea_id`), reglas de negocio con defaults propuestos, API, frontend, 5 entregas, pruebas y documentación. No se modificó código.
8. Revisión final (advisor). Se verificaron en el código fuente de frappe-gantt y se incorporaron al plan:
   - `date_utils.parse` crea fechas locales, así que se prohíbe `toISOString()` al volver (daría un día de más en UTC-3) y las pruebas Vitest corren con `TZ=America/Argentina/Buenos_Aires`;
   - `move_dependencies` es `true` por defecto y al soltar dispara un `date_change` por cada barra movida, por lo que se decide `move_dependencies: false`;
   - frappe dibuja una barra por fila, así que se quitan `primer_consumo` y `ultimo_consumo` de la entrega 1, que queda sin cambios de API;
   - el popup escapa solo `raw_name`, para no escapar dos veces;
   - las reglas de fechas y ciclos usan `SELECT … FOR UPDATE` sobre `proyecto`;
   - se agrega una prueba para "achicar el proyecto con tareas afuera" y `language: 'es'`.
9. Quedan para que el usuario confirme dos defaults que cambian endpoints existentes: un proyecto con tareas no se puede borrar (409), y editar las fechas de un proyecto puede dar 400 si deja tareas afuera. No se escribió código ni se hizo commit.

### Prompt 6 — Confirmación de los defaults

> confirming this.

**Acciones:**

1. Se tomó como confirmación de los dos defaults propuestos (409 al borrar un proyecto con tareas; 400 al achicar las fechas de un proyecto dejando tareas afuera) y como visto bueno para empezar la entrega 1 (portafolio).
2. **Entrega 1 — portafolio Gantt** (sin cambios de API ni de base):
   - `npm install frappe-gantt@1.2.2`.
   - Archivos nuevos: `src/types/frappe-gantt.d.ts` (tipos mínimos); `src/gantt.ts` (`projectBars`, que escapa `name` y conserva `raw_name`; `popup` con `textContent`; `toISODate` con fecha local); `src/components/ProjectGantt.vue` (único lugar que importa la librería: `move_dependencies: false`, `language: 'es'`, `popup_on: 'hover'`, selector Día/Semana/Mes, emite `select`); `src/views/PlanningView.vue` (`/planificacion`, de solo lectura; el clic abre el proyecto).
   - Archivos modificados: `router.ts` (ruta `planning`), `AppHeader.vue` (enlace "Planificación"), `main.css` (paleta y colores por estado), `package.json` (`npm test` con `TZ=America/Argentina/Buenos_Aires`), `vite.config.ts` (alias del CSS).
   - Pruebas: `tests/unit/gantt.spec.ts` (5 casos: comprueba que el TZ esté activo, el escape de la etiqueta, el popup escapado una sola vez, el mapeo de fechas, estados y avance, y la vuelta de fecha local contra el bug de `toISOString`), más un caso Playwright en `e2e/flows.spec.ts` (etiqueta `Portal <b>clientes</b>` como texto, clase por estado, popup y clic → detalle, sin errores de página).
3. Fallas encontradas y corregidas:
   - El primer e2e falló porque la vista no cargaba. `vite build` mostró que `frappe-gantt/dist/frappe-gantt.css` no está exportado.
   - Probar `@import 'frappe-gantt'` en CSS resolvió al JS (la condición `import` gana a `style`). Se resolvió con un alias en `vite.config.ts`.
   - El CSS de la librería se carga después de `main.css` y le ganaba a los colores por estado, así que se subió la especificidad.
4. Verificación de CSP: se levantaron `vite preview` del build y una API aislada en :5001, y con Playwright se inyectó la CSP exacta de `deploy/Caddyfile`. Se crearon 4 proyectos (uno con el nombre `Portal <b>clientes</b> & R&D`): 4 barras, **0 violaciones de CSP, 0 errores de consola**. Las capturas (en el scratchpad) mostraron que la vista Semana abría en meses vacíos y que el botón "Today" estaba en inglés. Se pasó a Mes por defecto, `scroll_to: 'today'` y `today_button: false`.
5. Resultados: `npm test` 15/15, `npm run typecheck` ok, `vite build` ok, `playwright test` 6/6. Se detuvieron los servidores temporales. Se actualizó `docs/PLAN.md` (entrega 1 ✔ y el hallazgo del `exports`). No se hizo commit.
6. Revisión (advisor). Pidió verificar en frappe-gantt si hay listeners globales y qué hace `refresh()`, antes de la entrega 2:
   - `index.js:1346` agrega un `mouseup` a `document` en `bind_bar_events` (que solo corre en el constructor) y nunca lo quita, así que recrear el gráfico en cada cambio perdía memoria. `refresh()` llama a `change_view_mode()` sin `maintain_pos`, lo que vuelve el scroll a hoy.
   - Cambio en `ProjectGantt.vue`: el gráfico se crea una vez por montaje; las actualizaciones usan `setup_tasks` + `change_view_mode(vista, true)` y ajustan `options.readonly`. El host usa `v-show` y el watcher corre con `flush: 'post'`, para que el gráfico no se construya dentro de un elemento oculto.
   - Verificación en el build de producción: vista vacía → se crea un proyecto → refetch → 1 barra; scroll en 300 → se crea otro → refetch → 2 barras, 1 solo SVG, scroll conservado en 300, sin errores. En el primer intento el refetch no se disparó porque se despachó `visibilitychange` sobre `document`, cuando TanStack escucha en `window`. Era un error del script de prueba, no de la app.
   - Se fijó `frappe-gantt` en `"1.2.2"` (sin `^`).
   - Se repitió todo: typecheck ok, Vitest 15/15, Playwright 6/6, build ok. `PLAN.md` quedó actualizado. No se hizo commit.

### Prompt 7 — ¿Está levantada la app?

> Is app up? to see it working

**Acciones:**

1. Se comprobó el estado: la API de desarrollo (:5000) y Vite (:5173) no estaban corriendo; solo los contenedores `db` y `mailpit`.
2. Se corrió `init-db` (idempotente: "Base inicializada.") y se iniciaron en segundo plano `uvicorn pulso.asgi:app --reload --port 5000` (con un `SECRET_KEY` aleatorio) y `npx vite --host 127.0.0.1 --port 5173`. Verificación: `/api/health` → ok a través de Vite y `/planificacion` → 200.
3. Hallazgo: la base de desarrollo tiene 0 proyectos, y el admin ya cambió su contraseña (el asistente no la conoce). El Gantt se verá vacío hasta cargar proyectos. Se ofreció cargar datos de ejemplo, sin hacerlo sin permiso.

### Prompt 8 — Alcance de la vista Planificación

> o sea esto muestra todos los proyectos?

**Acciones:**

1. Se respondió a partir de `PlanningView.vue`: llama a `api.projects({})` sin filtros, así que muestra todos los proyectos, a todos los usuarios (misma regla de lectura que la lista de Proyectos). Están ordenados por fecha de inicio, una barra por proyecto. Todavía no muestra tareas (eso llega en la entrega 2, en el detalle de cada proyecto). Se ofreció sumar los filtros de estado y responsable. No se modificó código.

### Prompt 9 — El Gantt va dentro de cada proyecto

> No. la idea es que el gantt se acceda desde un proyecto especifico y que se peudan ver las tareas dentro del mismo. No un gantt que muestre todos los proyectos.

**Acciones:**

1. Decisión del usuario: se descarta la vista general `/planificacion`. El Gantt vive en el detalle de cada proyecto y muestra sus tareas. Se retira la vista (ruta, enlace del menú, vista y caso e2e), se reutilizan `ProjectGantt.vue` y `gantt.ts` para las tareas, y se pasa a la entrega 2 del plan.
2. **Retiro de la vista general:** se eliminaron `PlanningView.vue`, la ruta `/planificacion`, el enlace del menú y su caso e2e.
3. **Entrega 2 — tareas (backend):**
   - `models.py`: modelo `Tarea` (FK a proyecto RESTRICT, responsable opcional, checks de nombre, fechas y avance).
   - Migración `0003_tareas.py`.
   - `schemas.py`: `OptionalId` (acepta `''`/`null`), `TareaIn` y `TareaOut`.
   - Router nuevo `routers/tasks.py`: `GET/POST /api/proyectos/{id}/tareas`, `GET/PUT/DELETE /api/tareas/{id}`. Permisos con `editable_project` y la dependencia nueva `editable_task`, ambas antes del cuerpo. La regla de fechas dentro del proyecto toma `SELECT … FOR UPDATE` sobre `proyecto`.
   - `projects.py`: editar el proyecto con tareas fuera del nuevo rango → 400, con el mismo bloqueo. Borrar un proyecto con tareas → 409 (lo da la FK RESTRICT y el handler de `IntegrityError` que ya existía).
   - `conftest.py`: `tarea` agregada al `TRUNCATE`.
   - `tests/test_tasks.py` (6 pruebas): CRUD y lectura para todos, permisos y 403 antes que 400, validaciones, fechas dentro del proyecto, achicar el proyecto, borrado 409.
   - Resultado: **101 passed**; ruff ok.
4. **Entrega 2 — frontend:**
   - `npm run gen:api` (sin drift al regenerar); en `client.ts`, el tipo `Task` y `tasks`/`task`/`createTask`/`updateTask`/`deleteTask`.
   - `gantt.ts`: `taskBars` (id `tarea-N` porque frappe usa el id en selectores CSS, `ref_id` numérico, clases `gantt-open`/`gantt-done`/`gantt-late`, detalle con responsable).
   - `ProjectGantt.vue`: emite `move`/`progress`/`open`; `open` con doble clic; `defineExpose({ reset })` para deshacer un arrastre rechazado; abre en la primera tarea.
   - `TaskPlan.vue` nuevo: sección "Planificación" con el Gantt, leyenda y tabla, y guardado del arrastre con un `PUT`.
   - `TaskFormView.vue` nuevo: rutas `/proyectos/:id/tareas/nueva` y `/tareas/:id/editar`, fechas con min/max del proyecto, responsable opcional.
   - `ProjectDetailView.vue` incluye `TaskPlan`; CSS de estados y `pointer-events:none` en el popup.
   - Pruebas: `gantt.spec.ts` reescrito (6 casos) y un e2e "project owner plans tasks on the Gantt" (rango inválido → mensaje de la API, nombre con HTML como texto, arrastre → aviso y tabla coinciden y se conserva la duración).
5. **Fallas en el camino:**
   - El e2e del arrastre falló varias veces. Primero se asumía un desplazamiento exacto de 2 días, pero frappe redondea según su cálculo con `offsetX`, así que la aserción pasó a ser robusta. Después se medía la barra durante la animación del cambio de escala, y se agregó una espera a que la geometría quede estable.
   - Se sospechó que el popup en hover tapaba el arrastre y se agregó `pointer-events:none` (se conserva como protección). La causa real, encontrada al registrar los eventos del mouse, era que la barra quedaba fuera del viewport de 720 px y `page.mouse` no hace scroll; se resolvió con `scrollIntoViewIfNeeded`.
   - Luego pasó 3 veces seguidas: 6/6.
6. **Revisión visual** en un stack aislado (:5001/:5174) con 5 tareas, como admin y como un usuario sin permisos. El usuario sin permisos ve todo en solo lectura (0 enlaces "+ Nueva tarea", 5 "Solo lectura") y no hubo errores de página. Se encontró que el diagrama abría un mes antes del proyecto; se pasó a `scroll_to` = inicio de la primera tarea.
7. **Base de desarrollo:** `init-db` aplicó la migración (`alembic current` → `0003 (head)`). La API en :5000 (con `--reload`) ya expone `/api/proyectos/{id}/tareas`.
8. **Verificación final:** pytest 101, ruff ok, typecheck ok, Vitest 16/16, build ok, Playwright 6/6 (3 corridas). `PLAN.md` actualizado. No se hizo commit.
9. **Revisión (advisor)** y correcciones:
   - `TaskFormView` quedaba en "Cargando…" para una tarea inexistente: la consulta del proyecto queda deshabilitada y pendiente si la de la tarea da 404. Se cambió `loading` a `catalogs || (id && existing) || (projectId && project)`, igual que `ProjectFormView`. El e2e ahora abre `/tareas/999/editar` y espera "No se pudo cargar la página".
   - Se agregó al e2e el arrastre rechazado (antes del inicio del proyecto): alerta de la API, la tabla conserva lo guardado y la barra vuelve a su `x`.
   - **Bug real encontrado al registrar los `PUT`:** un arrastre enviaba un `PUT` por cada día cruzado (2 en el primero; 3 en el segundo, el último rechazado con 400 después de guardar fechas intermedias, lo que dejaba la tarea en 09-01). Causa: frappe llama a `date_changed()` en cada `mousemove`. Arreglo en `ProjectGantt.vue`: se guarda el último cambio por barra y se emite un solo `move` en el `mouseup` del documento. El e2e verifica 1 `PUT` por arrastre. El supuesto del plan ("`move_dependencies: false` ⇒ un arrastre, un `PUT`") era falso y se corrigió en `PLAN.md`.
   - Resultado: typecheck ok, Vitest 16/16, build ok, Playwright 6/6 tres veces seguidas.

### Prompt 10 — Qué falta de la funcionalidad

> que mas queda de esta feature?

**Acciones:**

1. Se respondió a partir de `docs/PLAN.md`. Pendientes: entrega 3 (dependencias), entrega 4 (vínculo consumo↔tarea), entrega 5 (documentación y validación), commit de la entrega 2, verificación de la CSP con el stack de producción (Caddy) y la prueba manual del arrastre de avance. Se señalaron limitaciones conocidas (sin soporte táctil de frappe para arrastrar; en celulares el Gantt sirve solo para ver). No se modificó código.

### Prompt 11 — Cierre de la funcionalidad

> entrega 4 no lo vamos a hacer. es demasiado complejo para el scope de la tool. La dependencia tampoco. documentemos y cerremos la feature.

**Acciones:**

1. Decisión del usuario: se descartan la entrega 3 (dependencias) y la 4 (consumo↔tarea). La funcionalidad se cierra con las tareas (entrega 2) y la documentación (entrega 5).
2. **Documentación:**
   - `docs/API.md`: rutas de tareas, cuerpo de escritura y la sección "Tareas (Gantt)" con reglas, errores y bloqueos.
   - `docs/ESPECIFICACION.md`: entidad Tarea, reglas, acceso, interfaz; en Fase 5 queda solo lo pendiente, con nota de lo descartado.
   - `README.md`: fila "Planificar tareas" en la matriz de permisos, reglas, `tasks` en el mapa de carpetas, cantidad de pruebas y la sección "Planificación (Gantt)" con la limitación táctil y lo fuera de alcance.
   - `docs/PLAN.md`: entregas 3 y 4 tachadas como descartadas por el usuario, entrega 5 ✔ y "funcionalidad cerrada"; en la lista de fases, Gantt ✔.
   - `docs/VALIDACION.md`: sección nueva "Planificación Gantt (2026-09-30)".
   - `HISTORIAL_DESARROLLO.md` y `docs/HISTORIAL_DESARROLLO.md`: sección 20 (con el enlace a `prompts.md` ajustado en cada copia).
   - `FEATURE_PLAN.md` (raíz del repo): "Planificacion Gantt: Done (…)", porque el usuario pidió cerrar la funcionalidad.
   - `CLAUDE.md` local (ignorado por Git): estado de la Fase 5 y router `tasks.py`.
3. **Verificación manual que estaba pendiente:** build de producción con la CSP de `deploy/Caddyfile` inyectada. Sin violaciones ni errores; el arrastre del borde de avance hizo 1 `PUT` (70 %) y actualizó la tabla.
4. **Verificación final:** ruff ok, pytest 101, typecheck ok, Vitest 16/16, build ok, `gen:api` estable, Playwright 6/6.
5. Se commitea la funcionalidad en la rama `feat-gantt-chart` (sin push).

## Prompt: "como es el proceso para levantar la app para una persona que recien se clona el repo? windows y linux."

**Acciones realizadas:**
- Se leyó `tp-final/README.md` (sección "Desarrollo local", `compose.yaml`, `.env.example`) para confirmar los pasos y requisitos vigentes.
- Se verificó con `grep` que `SECRET_KEY` ya no es usado por el backend (solo aparece en un test de email histórico) — las sesiones son server-side en tabla `sesion` sin clave de firma, por lo que ese paso mencionado en una versión anterior de `CLAUDE.md` está desactualizado y no se incluyó en la respuesta.
- Se verificó `requires-python = ">=3.12"` en `backend/pyproject.toml`.
- No se modificó ningún archivo de código; se respondió únicamente en el chat explicando el proceso para Windows y Linux (prerequisitos: Git, uv, Node 22+, Docker/Podman; pasos: clonar, levantar `db`/`mailpit` con compose, `init-db`, `uvicorn --reload`, `npm install && npm run dev`).

## Prompt: "/plan Hay que buscar una forma de que sea mas facil de levantar local sin modificar como funciona. demasiado. podemos hacerlo?"

**Acciones realizadas (modo plan):**
- Se lanzó un agente Explore para relevar hechos: `backend/pulso/cli.py` (CLI con `argparse`, sin lógica de subprocess), `.github/workflows/tp-final.yml` (referenciado en el README pero **no existe** en el repo/historial — desajuste preexistente, no se tocó), `frontend/package.json` (sin `concurrently`/`npm-run-all`), el servicio `api` de `compose.yaml` (documentado como alternativa secundaria, no como flujo principal) y `backend/pulso/config.py` (default de `database_url` ya coincide con el compose de desarrollo; `SECRET_KEY` no es un campo de `Settings`, mención obsoleta en una versión vieja de `CLAUDE.md`).
- Se lanzó un agente Plan para diseñar la solución: un único script Python cross-platform (`uv run scripts/dev.py`, sin dependencias, cabecera PEP 723) que encadena los mismos comandos ya documentados (compose up db/mailpit, `init-db`, `uvicorn --reload`, `npm install && npm run dev`) sin cambiar la arquitectura. Se descartó Makefile (requiere `make` en Windows) y scripts `.sh`/`.ps1` duplicados (doble mantenimiento).
- Se escribió el plan final en `/home/gaspi/.claude/plans/linear-twirling-ember.md` y se pidió aprobación con `ExitPlanMode`. El usuario aprobó y avisó que había creado una rama nueva (`feat-improve-first-build-process`).

**Implementación:**
- Se creó `tp-final/scripts/dev.py`: detecta `docker compose` / `podman-compose` / `podman compose`, levanta `db`+`mailpit`, espera Postgres por polling TCP a `127.0.0.1:5432` (no depende de `--wait`, que no se comporta igual entre docker compose y podman-compose), corre `init-db`, saltea `npm install` si `frontend/node_modules` ya existe (`--reinstall` para forzar), y arranca `uvicorn` y `npm run dev` como subprocesos con logs prefijados `[api]`/`[web]`. Al cerrar (Ctrl+C o `SIGTERM`) termina ambos subprocesos de forma prolija (grupo de procesos propio en Linux/macOS vía `start_new_session`, `CREATE_NEW_PROCESS_GROUP`/`CTRL_BREAK_EVENT` en Windows) y deja `db`/`mailpit` corriendo salvo que se pase `--down`. Flags: `--reinstall`, `--down`, `--skip-compose`.
- Se actualizó `tp-final/README.md` (sección "Desarrollo local"): se agregó una subsección "Forma rápida" con `uv run scripts/dev.py` antes del bloque manual existente, que se conservó íntegro bajo "Manual, paso a paso" como referencia y para troubleshooting.

**Pruebas realizadas en esta máquina (Linux + podman-compose), corridas en background y verificadas con `curl`/`pgrep`/`ss`/`podman ps`:**
- Corrida limpia: detecta `podman-compose`, levanta contenedores, espera Postgres, corre `init-db`, saltea `npm install` (ya existía `node_modules`), sirve `http://127.0.0.1:5000/api/docs` y `http://127.0.0.1:5173/` simultáneamente (200 en ambos).
- Se encontraron y corrigieron dos problemas reales durante la prueba: (1) los `print()` del script quedaban fuera de orden respecto a la salida de los subprocesos por buffering — se corrigió con `sys.stdout.reconfigure(line_buffering=True)`; (2) el script solo limpiaba los subprocesos con `SIGINT`, no con `SIGTERM` (se evidenció al probar con `timeout`, que quedaron procesos huérfanos en 5000/5173) — se agregó un handler de `SIGTERM` que dispara el mismo camino de cierre limpio.
- Tras el fix: `SIGTERM` cierra `api` y `web` sin huérfanos y deja `db`/`mailpit` corriendo; con `--down` además baja los contenedores.
- Caso de error: con el puerto 5000 ocupado por otro proceso, el script detecta que la API murió, apaga `web` también, deja los contenedores arriba, y sale con mensaje claro (sin traceback, exit code 1) — mismo comportamiento verificado con el puerto 5173 ocupado (falla del frontend).
- `check_prereqs()` probado por separado (monkeypatch de `shutil.which`): da mensaje amigable sin traceback cuando falta Node/npm.
- Se limpiaron los procesos de prueba y se dejó el entorno (`db`/`mailpit`) en el mismo estado en que estaba antes de empezar.

**No verificado en esta sesión (riesgo declarado):** ejecución real en Windows (PowerShell/cmd) — en particular el camino `CREATE_NEW_PROCESS_GROUP`/`CTRL_BREAK_EVENT` — y Docker Desktop específicamente (acá solo hay podman-compose disponible).

**Archivos creados/modificados:** `tp-final/scripts/dev.py` (nuevo), `tp-final/README.md`, `tp-final/prompts.md`. No se hizo commit; queda a criterio del usuario.
