# Plan de separación frontend / backend

## Objetivo

Reemplazar la interfaz renderizada en Flask por un frontend independiente en HTML, JavaScript y CSS, conservando SQLite, usuarios, proyectos y reglas funcionales.

## Implementación

1. Convertir blueprints Flask a API `/api`, con JSON, códigos HTTP y serialización explícita que excluye hashes.
2. Mantener cookies HttpOnly y CSRF; bootstrap de sesión y token por GET, renovación en login/logout/cambio de contraseña.
3. Crear frontend con módulos ES: cliente HTTP, componentes seguros y navegación/formularios. Mantener pantallas, permisos visibles y diseño adaptable.
4. Retirar plantillas Jinja y mover estilos al frontend. Servirlo como componente separado con proxy `/api` al backend, sin lógica de negocio.
5. Migrar pruebas funcionales al contrato JSON y agregar pruebas del cliente y del proxy.
6. Validar ambos componentes en navegador con base temporal; iniciar la aplicación real conservando la base existente.
7. Actualizar documentación de ejecución y contrato. No realizar operaciones Git que requieran la autorización rechazada anteriormente.

## Compatibilidad

No hay cambio de esquema ni reinicialización destructiva. La URL de la interfaz pasa al puerto 8000; el 5000 contiene solamente API. Cambiar SECRET_KEY al reiniciar invalida sesiones, pero mantiene cuentas, contraseñas y datos. Los endpoints HTML anteriores se reemplazan por el contrato documentado en API.md.

---

# Plan de replataforma (2026-09-23): FastAPI + Vue + PostgreSQL

## Motivo

La versión anterior se diseñó como una aplicación local. El nuevo objetivo es hostearla para un equipo chico y sumar las funcionalidades del roadmap (`FEATURE_PLAN.md`): reporting de plan vs. ejecución, desvíos y proyecciones, cargas masivas, Gantt y alertas por correo. El stack tenía tres limitaciones para eso:

- no había migraciones de esquema (solo `CREATE TABLE IF NOT EXISTS`);
- el frontend se armaba concatenando `innerHTML`, lo que no escala a vistas complejas;
- SQLite y un proxy artesanal no alcanzan para un despliegue real.

## Decisiones (acordadas con el usuario)

| Tema | Decisión | Motivo |
|---|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic | Tipos y OpenAPI automáticos (cliente tipado para el frontend) y migraciones versionadas |
| Base de datos | PostgreSQL 16 | Escrituras concurrentes con varios workers, bloqueos de fila y backups con `pg_dump` |
| Frontend | Vue 3 + TypeScript + Vite, Pinia y TanStack Query | Componentes para vistas complejas (Gantt, reportes) con una curva de aprendizaje suave |
| Autenticación | Sesión por cookie en el servidor + CSRF | Es lo más seguro para una SPA del mismo origen; mantiene el diseño anterior |
| Infraestructura | Docker Compose + Caddy | HTTPS automático, un solo origen y portable a cualquier VPS |
| Estilos | Se mantuvo el CSS propio + Bootstrap | Paridad visual; PrimeVue y ECharts se evaluarán en la Fase 5 |
| Gantt (Fase 5) | Componente propio `<ProjectGantt>` que envuelve SVAR Gantt o frappe-gantt | Poder cambiar de librería sin tocar las páginas |

## Fases

1. **Fundamentos:** `backend/` con uv, compose de desarrollo, migración base de Alembic y CI. ✔
2. **Paridad del backend:** el mismo contrato de API.md, la suite Flask portada, `init-db` e `import-sqlite`. ✔
3. **Paridad del frontend:** las mismas pantallas y reglas en Vue, con pruebas Vitest y Playwright. ✔
4. **Despliegue:** Caddy, `compose.prod.yaml` y backups; se retira la versión Flask. ✔
5. **Funcionalidades:** reporting → CSV → Gantt → alertas (worker + SMTP). Gantt ✔ (2026-09-30, tareas por proyecto; ver el plan de planificación más abajo). El resto queda **pendiente para una fecha futura**.
6. **Documentación:** README, API, especificación, este plan y la validación. ✔

## Compatibilidad

- Se conservan los nombres de tablas, columnas y rutas de la API.
- Cambios visibles en el contrato:
  - `es_admin` y `debe_cambiar_password` son booleanos JSON;
  - `responsable` no numérico devuelve 400;
  - un ID de ruta no numérico devuelve 404;
  - los 500 siempre se devuelven como JSON.
- Los datos existentes se importan con `import-sqlite`, conservando IDs y contraseñas.
- La interfaz de desarrollo pasa al puerto 5173 (Vite) y la API sigue en el 5000.

---

# Plan de planificación Gantt (2026-09-30) — rama `feat-gantt-chart`

## Motivo

`ESPECIFICACION.md` promete "Planificación Gantt: tareas, dependencias y vínculo opcional de consumos con tareas". Hoy el modelo no tiene tareas planificadas: solo `proyecto` (fechas, horas, avance manual) y `consumo` (horas reales, con un texto libre `tarea`). El Gantt necesita tablas nuevas.

**Desvío respecto de la Fase 5:** allí el orden previsto era reporting → CSV → Gantt → alertas. Por decisión del usuario, el Gantt se adelanta. Reporting y CSV no dependen de él.

## Decisiones (acordadas con el usuario)

| Tema | Decisión | Motivo |
|---|---|---|
| Alcance | Tareas y dependencias, en entregas incrementales (una por commit) | Cumple la especificación sin un cambio grande de una sola vez |
| Librería | frappe-gantt 1.2.2 (MIT, SVG, sin dependencias), envuelta en `<ProjectGantt>` | Liviana, dibuja dependencias y progreso, permite arrastrar; su CSS plano encaja con el estilo actual |
| Permisos | Todos consultan; crean/editan/borran tareas y dependencias el responsable del proyecto o un administrador | Es la misma regla que editar el proyecto (`editable_project`) |

## Hechos verificados de frappe-gantt 1.2.2

- No trae tipos TypeScript: hace falta un `src/types/frappe-gantt.d.ts` propio con lo que se usa.
- La fecha de fin sin hora se toma **inclusiva** (suma 24 h), igual que en el backend. `on_date_change(task, start, end)` devuelve `end` como el último segundo del día, así que se formatea `YYYY-MM-DD` sin restar un día. `date_utils.parse` arma fechas **locales** a partir de las partes del texto, así que para volver se usan `getFullYear`/`getMonth`/`getDate` y **nunca** `toISOString()`, porque en UTC-3 correría el fin un día. Las pruebas Vitest de fechas corren con `TZ=America/Argentina/Buenos_Aires`, ya que en CI (UTC) la versión incorrecta también pasa.
- Eventos: `on_click`, `on_date_change`, `on_progress_change`, `on_view_change`. Opciones `readonly`, `readonly_dates`, `readonly_progress`, `view_mode`, `language`, `popup`, `custom_class`.
- **Riesgo XSS:** la etiqueta de la barra (`bar.js`) y el popup por defecto usan `innerHTML` con `task.name`. Los nombres son texto del usuario, así que el adaptador **escapa HTML** en `name` y define un `popup` propio que también escapa. El nombre sin escapar va en una clave aparte (`raw_name`), y el popup escapa **solo** esa clave, para no escapar dos veces (`R&D` no debe verse como `R&amp;D`). Lleva pruebas Vitest con un nombre `<img onerror>` y otro con `&`.
- `move_dependencies` viene en `true`: al soltar, `date_changed()` corre para cada barra movida (`index.js`, mouseup), o sea, N eventos y N `PUT`, que pueden fallar a medias. Como la regla 2 no impone el orden fin→inicio, se usa **`move_dependencies: false`**. **Corrección (entrega 2):** eso no alcanza para "un arrastre, un `PUT`". `update_bar_position` llama a `date_changed()` en cada `mousemove`, y `date_change` se dispara por cada día que cruza la barra (un e2e registró 3 `PUT` en un solo arrastre). `<ProjectGantt>` guarda el último cambio por barra y emite un solo `move` en el `mouseup` del documento. El e2e verifica un `PUT` por arrastre. `progress_change` sí se dispara una sola vez, al soltar.
- `language` viene en `'en'`: se usa `'es'`.
- El `exports` de la librería solo expone el CSS bajo la condición `style`, que figura después de `import`, así que ni `frappe-gantt/dist/frappe-gantt.css` ni un `@import 'frappe-gantt'` funcionan en Vite: hay un alias `frappe-gantt.css` en `vite.config.ts`. Como ese CSS se carga en diferido (después de `main.css`), los colores por estado usan `.gantt .bar-wrapper.gantt-<estado>` para ganarle en especificidad.
- El constructor agrega un listener `mouseup` a `document` que nunca se quita (`index.js`, `bind_bar_events`), y `refresh()` vuelve a hoy con el scroll. Por eso `<ProjectGantt>` crea el gráfico **una vez** por montaje y actualiza con `setup_tasks` + `change_view_mode(vista, true)`, que conserva el scroll. Es importante para la entrega 2, donde cada arrastre invalida la consulta. La versión queda fijada en `1.2.2` (sin `^`), porque los tipos, el alias y estos hechos dependen de ella.
- CSP de Caddy (`style-src 'self'; style-src-attr 'unsafe-inline'`): la librería no inserta `<style>`, y su CSS se importa y Vite lo empaqueta. Los `style=` y `element.style` quedan permitidos. Aun así se verifica en el stack de producción, porque Vite dev no aplica la CSP.

## Modelo de datos (migración `0003_tareas`)

- `tarea`: `tarea_id`, `proyecto_id` → `proyecto` (RESTRICT), `tarea_nombre` (no vacío), `fecha_inicio`, `fecha_fin` (`>= fecha_inicio`), `porcentaje_avance` (0–100, default 0), `recurso_id` → `recurso`, opcional (responsable de la tarea). Sin columna `orden`: se ordena por `fecha_inicio`, `tarea_id`.
- `dependencia`: `predecesora_id` y `sucesora_id` → `tarea` (**CASCADE**), PK compuesta, `CHECK predecesora_id <> sucesora_id`. Solo fin→inicio, que es lo único que dibuja frappe.
- `consumo.tarea_id` → `tarea`, nullable (RESTRICT). Se hace en la entrega 4.

## Reglas de negocio (defaults propuestos)

1. **Fechas de la tarea:** deben quedar dentro de las del proyecto, y la API devuelve 400 si no. Es distinto de los consumos, que admiten fechas fuera del rango, porque una tarea es plan y no ejecución. Si al editar el proyecto se achica su rango y deja tareas afuera, se rechaza con 400 (alternativa: solo avisar). Para evitar carreras (una tarea que se guarda mientras se achica el proyecto), ambas operaciones toman `SELECT … FOR UPDATE` sobre la fila de `proyecto`, igual que la regla del último administrador.
2. **Dependencias:** misma tarea → 400; tareas de distintos proyectos → 400; ciclos → 400 (búsqueda en el grafo del proyecto antes de insertar, con el mismo bloqueo de la fila `proyecto` para que dos altas simultáneas no formen un ciclo); duplicada → 409. Que la sucesora empiece después de que termine la predecesora **no se impone**: el Gantt lo muestra y el reporting futuro lo marcará como desvío.
3. **Borrado:** se mantiene la regla "no se eliminan registros con referencias". Un proyecto con tareas no se puede borrar (409, hay que borrar primero las tareas), ni una tarea con consumos vinculados. Borrar una tarea borra sus dependencias en cascada. Este cambio se documenta.
4. **Avance del proyecto:** sigue siendo manual e independiente de las tareas. No se calcula desde ellas.
5. **Consumo ↔ tarea (entrega 4):** el texto libre `consumo.tarea` se conserva, porque sigue siendo la descripción del trabajo. `tarea_id` es un vínculo opcional; la tarea tiene que ser del mismo proyecto (400) y, si cambia el proyecto del consumo, el vínculo se vuelve a validar. El permiso sigue en `own_consumption`.

## API

- `GET /api/proyectos/{id}/tareas` → tareas y dependencias del proyecto (lectura para todos).
- `POST /api/proyectos/{id}/tareas` (dependencia `editable_project`).
- `PUT`/`DELETE /api/tareas/{tarea_id}`: nueva dependencia `editable_task` que carga la tarea y comprueba el dueño de su proyecto **antes** de validar el cuerpo (403 antes que 400, igual que el resto).
- `POST /api/tareas/{tarea_id}/dependencias` `{predecesora_id}` y `DELETE /api/tareas/{tarea_id}/dependencias/{predecesora_id}`.
- Portafolio: `GET /api/proyectos` ya devuelve fechas, estado y avance, y alcanza. frappe dibuja una sola barra por fila, así que la ejecución real (min/max de fechas de consumo) queda para el reporting.
- Validadores Pydantic con `PydanticCustomError('pulso', …)` y mensajes en castellano, igual que en `schemas.py`. Después de cada cambio de API se corre `npm run gen:api`, porque CI falla si hay diferencias.

## Frontend

- `components/ProjectGantt.vue`: único lugar que importa frappe-gantt (y `frappe-gantt/dist/frappe-gantt.css`). Recibe tareas y dependencias tipadas y `readonly`, y emite `date-change`, `progress-change` y `select`. Recrea el gráfico cuando cambian los datos, lo destruye en `onBeforeUnmount` y tiene un selector de vista (Día/Semana/Mes).
- `gantt.ts`: función pura que mapea API → tareas de frappe (escapa nombres; `custom_class` por estado o por atraso) y fechas de vuelta. Se prueba con Vitest.
- `ProjectDetailView`: nueva sección "Planificación" con el Gantt y la lista de tareas. `readonly` se toma del `editable` que ya existe. Al arrastrar se hace `PUT /tareas/{id}` con optimismo y se invalida `['proyecto', id]` / `['tareas', id]`; si falla, el aviso de error ya existente y se recarga.
- `TaskFormView` (`/proyectos/:id/tareas/nueva`, `/tareas/:id/editar`) con `FormShell`, `TextField` y `SelectField`. Rutas nuevas en `router.ts`.
- Sin vista de portafolio: el Gantt existe solo dentro de cada proyecto (decisión del usuario).

## Entregas (una por commit)

1. ~~**Portafolio:** vista `/planificacion` con una barra por proyecto.~~ Se implementó y **el usuario la descartó** (2026-09-30): el Gantt se accede solo desde cada proyecto y muestra sus tareas. Se retiraron la vista, la ruta, el enlace y su e2e; `ProjectGantt` y `gantt.ts` se reutilizaron para las tareas.
2. **Tareas:** migración 0003 (`tarea`), modelos y esquemas, CRUD con `editable_task`, regla de fechas dentro del proyecto, la regla de borrado del proyecto, el Gantt del proyecto con arrastre y el formulario de tarea. ✔ (2026-09-30; sin la columna `orden`: las tareas se ordenan por fecha de inicio. La edición se abre con doble clic, porque frappe dispara `click` también al soltar un arrastre)
3. ~~**Dependencias:** tabla `dependencia`, validación de mismo proyecto y de ciclos, flechas en el Gantt.~~ **Descartada por el usuario** (2026-09-30): excede el alcance de la herramienta.
4. ~~**Consumo ↔ tarea:** `consumo.tarea_id`, selector de tarea en el consumo.~~ **Descartada por el usuario** (2026-09-30): demasiado compleja para el alcance de la herramienta.
5. **Documentación y validación:** ver abajo. ✔ (2026-09-30)

**Estado: funcionalidad cerrada** con las entregas 2 y 5. Las reglas 2 y 5 y la tabla `dependencia` no se implementaron.

## Pruebas

- **pytest:** CRUD de tareas; permisos (usuario → 403, responsable → OK en su proyecto y 403 en otro, admin → OK); 403 antes que 400; fechas fuera del proyecto; `PUT /proyectos` que achica el rango con tareas afuera (400); dependencia con sí misma, entre proyectos, ciclo y duplicada; borrado de un proyecto con tareas (409), de una tarea con consumos (409) y cascada de las dependencias; consumo con tarea de otro proyecto (400).
- **Vitest:** el mapeo de `gantt.ts` (escape XSS sin doble escape, fechas inclusivas en ambos sentidos con `TZ` de Buenos Aires, clases).
- **Playwright:** el responsable crea dos tareas, las vincula, las ve en el Gantt y un usuario común lo ve en solo lectura.
- **Manual:** stack `compose.prod.yaml` detrás de Caddy, sin violaciones de CSP en la consola. `import-sqlite` sigue funcionando (las tablas nuevas quedan vacías).

## Documentación a actualizar

`docs/API.md` (endpoints y errores nuevos), `docs/ESPECIFICACION.md` (el Gantt deja de estar pendiente, y reglas 1–5), `README.md` (fila "Planificar tareas y dependencias" en la matriz de permisos y la regla de borrado), `docs/VALIDACION.md`, el estado de este plan y `prompts.md`. `FEATURE_PLAN.md` es del usuario: se le propone pasar "Planificacion Gantt" a Done, pero no se edita sin su visto bueno.

## Reporting: dashboard por proyecto (2026-10-07)

Decisiones del usuario: pantalla nueva `/proyectos/:id/dashboard` enlazada desde el detalle; los cuatro grupos de bloques en la primera versión (salud/desvíos, horas por período y distribución, ritmo y proyecciones, salud de tareas); gráficos con una librería (Chart.js + vue-chartjs).

- Los cálculos viven en el backend (`reports.py`, `GET /api/proyectos/{id}/reporte`) y reutilizan la regla de prorrateo del gráfico de horas acumuladas (`projectHours.ts`), para que ambos coincidan.
- La fecha de fin proyectada se calcula en el frontend con la misma regresión lineal del gráfico (`projectedEndDate`); en la pantalla cada ritmo muestra su origen (ventana de 28 días vs. regresión sobre toda la historia).
- Límites: no hay horas por tarea del Gantt ni desvíos por dependencias (ambos descartados).
- Pendiente de confirmar con el usuario: los umbrales del semáforo (≥ 1 en orden, ≥ 0,85 atención).
