# Validación

## Planificación Gantt (2026-09-30)

### Automatizada

- **Backend:** **101 pruebas aprobadas** (6 nuevas en `tests/test_tasks.py`):
  - CRUD de tareas; lectura para todos, ordenadas por fecha de inicio;
  - permisos (usuario común → 403, responsable del proyecto y administrador → OK), 403 antes que 400, 404 de proyecto y tarea;
  - validaciones en español (nombre vacío, avance fuera de rango o booleano, fechas invertidas o inválidas, responsable inexistente);
  - fechas de la tarea dentro del proyecto, achicar un proyecto dejando tareas afuera (400) y borrar un proyecto con tareas (409);
  - la prueba de migraciones confirma que `0003_tareas` coincide con los modelos.
  - `ruff check` y `ruff format --check` sin observaciones.
- **Frontend:** `vue-tsc` sin errores, `vite build` correcto, `gen:api` estable (sin diferencias al regenerar) y Vitest con **16 pruebas aprobadas**. `gantt.spec.ts` corre con `TZ=America/Argentina/Buenos_Aires` y verifica que el TZ esté activo. Cubre el escape de la etiqueta de la barra, el popup escapado una sola vez, las fechas inclusivas y su vuelta como fecha local (el bug de `toISOString` en UTC-3), y las clases en curso, terminada y atrasada.
- **E2E:** **6 pruebas aprobadas**, tres corridas seguidas. El caso nuevo es "project owner plans tasks on the Gantt":
  - rango inválido → mensaje de la API;
  - nombre con HTML mostrado como texto;
  - arrastre → aviso y tabla coinciden, se conserva la duración y hay **un solo `PUT` por arrastre**;
  - arrastre antes del inicio del proyecto → error de la API y la barra vuelve a su lugar;
  - `/tareas/999/editar` muestra el error en lugar de quedar cargando.

### Manual

- **Build de producción** (`vite preview`) con la CSP exacta de `deploy/Caddyfile` inyectada en el navegador: sin violaciones ni errores de consola. El arrastre del borde de avance hizo un solo `PUT` (70 %) y actualizó la tabla.
- **Capturas:** como administrador (acciones de edición) y como usuario sin permisos (0 botones de alta, todo "Solo lectura"). Las vistas Semana y Mes abren en la primera tarea.
- **Base de desarrollo:** migrada con `init-db` a `0003 (head)`.

### Problemas encontrados y corregidos

- El `exports` de frappe-gantt oculta su CSS: se resolvió con un alias en `vite.config.ts`.
- El CSS de la librería se carga después del propio y pisaba los colores: se subió la especificidad.
- El constructor de frappe-gantt deja un listener en `document`: el gráfico se crea una vez por montaje y se refresca conservando el scroll.
- Un arrastre enviaba un `PUT` por cada día cruzado y podía guardar fechas intermedias: se acumula y se emite al soltar.
- El formulario quedaba en "Cargando…" para una tarea inexistente.

### Sin verificar

- El stack completo de producción (Caddy + imágenes) no se levantó en esta etapa. La CSP se verificó inyectándola en el navegador sobre el build.
- Arrastrar en pantallas táctiles no está soportado por frappe-gantt.

## Replataforma FastAPI + Vue + PostgreSQL (2026-09-23)

### Automatizada

- **Backend** (`cd backend && uv run pytest -q`): **78 pruebas aprobadas**, cada corrida sobre una base Postgres temporal.
  - Incluye toda la suite Flask portada: contrato JSON, login/logout, CSRF en POST/PUT/DELETE, permisos directos, CRUD, validaciones límite, integridad referencial, último administrador, duplicados sin distinguir mayúsculas, agregados, IDs no reutilizados, hashes nunca expuestos, JSON inválido o que no es un objeto, 415 e inicialización idempotente.
  - Pruebas nuevas:
    - flags de la cookie de sesión y login sin distinguir mayúsculas;
    - cierre de otras sesiones al cambiar la contraseña;
    - aceptación y re-hash de hashes werkzeug heredados;
    - mensajes de validación en español y orden de catálogos;
    - 404 por ID no numérico, 413 y 500 siempre como JSON;
    - que las migraciones Alembic coincidan con los modelos, y downgrade/upgrade.
- `ruff check` y `ruff format --check`: sin observaciones.
- **Frontend:** `vue-tsc` sin errores, `vite build` correcto y Vitest con **9 pruebas aprobadas**. Cubren el cliente HTTP (CSRF rotado solo en mutaciones, cookies del mismo origen, 204, errores sin reintento, errores de red y respuestas inválidas), el escape de nombres y tareas hostiles, las acciones según permisos y las reglas de navegación.
- **E2E** (`npm run test:e2e`, Playwright + Chromium, API real con una base `pulso_e2e` recreada en cada corrida): **5 pruebas aprobadas**.
  1. Cambio de contraseña obligatorio en el primer ingreso, con el bloqueo de otras rutas.
  2. El administrador crea un recurso, un rol y un proyecto; el nombre hostil se muestra escapado.
  3. Un usuario común registra horas: un error de fechas conserva el formulario, se registran 25,5 h sobre 20 h (exceso de 5,5 h) sin alterar el avance manual del 40 %, se lo redirige desde una ruta de admin y cierra sesión.
  4. Recarga de una URL profunda y eliminación de un consumo.
  5. Login en un teléfono (Pixel 7) sin scroll horizontal.

### Migración de datos

La base real `instance/proyectos.sqlite` se copió y se importó en una base Postgres descartable. Se importaron 1 recurso, 3 roles, 1 proyecto y 1 consumo. Los agregados coinciden: 560 h requeridas, 12 h consumidas y saldo de 548 h. La secuencia de IDs quedó ajustada y el hash heredado se conservó; un `init-db` posterior no creó otro administrador. Además, el frontend anterior funcionó sin cambios contra la API FastAPI.

### Stack de producción (local, podman)

`compose.prod.yaml` en los puertos 8080/8443 con dominio `localhost`:

- HTTPS con la CA local de Caddy.
- CSP, HSTS y `X-Frame-Options` en las páginas.
- Assets con caché inmutable y páginas con `no-cache`.
- Cookie `Secure`, 413 para cuerpos de más de 1 MB y `/api/docs` accesible.
- Backups:
  - Primera versión: el dump inicial podía correr antes de las migraciones, y `&&` solo miraba el código de salida de gzip.
  - Corrección: el servicio espera a `alembic_version`, usa `pipefail` y escribe a un archivo temporal, con `--clean --if-exists`.
  - Verificado: el primer dump automático contiene las 6 tablas. Se crearon datos reales por la API (cambio de contraseña, rol y proyecto) y se generó un dump con ellos.
  - Se eliminaron los volúmenes y se levantó un stack nuevo, que `init-db` inicializó con su propio admin. Luego se restauró con el comando del README: sin errores, el login funcionó con la contraseña respaldada, el proyecto volvió y quedó un único administrador.
- En Chromium: login y cambio de contraseña forzado sin errores de CSP ni de consola.

Los contenedores y volúmenes de prueba se eliminaron al terminar.

### Revisión visual

Capturas de login, listado y detalle de proyecto: el diseño coincide con la versión anterior.

---

## Versión anterior: separación frontend / API Flask (histórico)

### Automatizada

- `python -m pytest -q tests/test_app.py`: 66 pruebas aprobadas de API JSON, permisos, CRUD, validaciones, CSRF, hashes no expuestos, integridad, agregados y persistencia.
- `python -m pytest -q tests/test_frontend_server.py`: 2 pruebas aprobadas del servidor estático/proxy con llamadas HTTP reales, cookies, login, escrituras y API desconectada.
- `node --test tests/frontend.test.mjs`: 2 pruebas aprobadas del cliente JavaScript: escape de entradas, JSON, cookies, renovación CSRF, DELETE 204 y errores de red/servidor sin reintentar escrituras.
- Compilación Python y comprobación de sintaxis de los tres módulos JavaScript.

### Navegador

Revisión contra frontend y API separados en puertos de prueba, con SQLite temporal:

- Login desde HTML/JavaScript y carga del tablero mediante API.
- Creación de proyecto con 20 horas y 40 % de avance manual.
- Intento de consumo con cero horas: error visible sin perder datos del formulario.
- Consumo de 25,5 horas fuera del período previsto: exceso de 5,5 horas y avance manual conservado en 40 %.
- Recarga de URL de detalle: rutas del frontend y sesión siguen funcionando.
- Alta y edición de rol mediante POST y PUT JSON.
- Filtro por estado sin resultados y limpieza del filtro.
- Revisión a 390 × 844 píxeles: navegación, indicadores y filtros sin desbordamiento horizontal de página.

Los datos de prueba no se cargan en la base del usuario. No se cambia el esquema de SQLite ni se restablecen contraseñas existentes. La interfaz pasa al puerto 8000 y la API al 5000.

### Historial

La versión inicial Flask/Jinja tuvo 49 pruebas aprobadas; esa suite fue adaptada al contrato JSON, por lo que los conteos no se suman. En esta versión se retiran las plantillas y la navegación por formularios HTML del backend.

## Email de recursos y retiro de clave heredada (2026-09-24)

- Se eliminó la exigencia de SECRET_KEY; las sesiones continúan en PostgreSQL.
- Migración 0002 aplicada en la base local: agrega email nullable y conserva los campos y contraseñas existentes.
- 95 pruebas de backend aprobadas. Incluyen email válido/inválido, normalización, alta/edición/lectura y rechazo sin alterar el dato anterior.
- Frontend: compilación correcta, 9 pruebas previas y 1 nueva prueba del formulario aprobadas.
- Ruff check y format --check sin observaciones. OpenAPI y tipos del frontend regenerados.
- La conexión local de pruebas requirió 127.0.0.1 en lugar de localhost. Los E2E completos no se volvieron a ejecutar; su flujo de alta fue actualizado para cargar email.
