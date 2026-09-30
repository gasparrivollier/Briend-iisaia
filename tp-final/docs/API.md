# API JSON de Pulso

Prefijo `/api`. Todas las respuestas son JSON, salvo un DELETE exitoso (204 sin cuerpo). El backend (FastAPI) no genera HTML ni redirige al login. El frontend llama rutas de su mismo origen: Caddy en producción y el servidor de Vite en desarrollo reenvían `/api/*` a la API.

El esquema OpenAPI completo, fuente del cliente tipado del frontend, se sirve en `/api/openapi.json`, con documentación interactiva en `/api/docs`. Este documento resume el contrato y las reglas que el esquema no expresa.

## Autenticación y CSRF

1. `GET /api/session` devuelve `{ "user": null, "csrf_token": "..." }` y, si no había sesión, establece la cookie `pulso_session` (HttpOnly, SameSite=Lax y `Secure` en producción). La sesión se guarda en el servidor: una sesión anónima dura 2 h y una autenticada 7 días (`SESSION_DAYS`).
2. `POST /api/login` recibe `{ "recurso_nombre": "admin", "password": "..." }`. Enviar cookie, `Content-Type: application/json` y `X-CSRF-Token` obtenido en el paso anterior.
3. La respuesta contiene `user` y un nuevo `csrf_token`. Login, logout y cambio de contraseña emiten una cookie nueva y un token nuevo, que hay que actualizar. El cambio de contraseña (propio, o restablecido por un administrador) cierra las demás sesiones de esa cuenta. El login no distingue mayúsculas en el nombre de usuario.
4. Todas las mutaciones (POST, PUT, DELETE) requieren cookie, token y objeto JSON. Para DELETE/logout, enviar `{}`.
5. `user` expone únicamente `recurso_id`, `recurso_nombre`, `es_admin` y `debe_cambiar_password`; estos dos últimos son booleanos JSON (`true`/`false`; la versión Flask devolvía `1`/`0`). Si el cambio está pendiente, solo se permiten session, login, logout y password.

| Método | Ruta | Entrada / salida |
|---|---|---|
| GET | `/api/health` | `{ "status": "ok" }` si la API y la base responden (sin sesión) |
| GET | `/api/session` | Usuario actual o null y token CSRF |
| POST | `/api/login` | Usuario/contraseña → sesión |
| POST | `/api/logout` | `{}` → usuario null y token nuevo |
| PUT | `/api/password` | `actual`, `password`, `confirmacion` → sesión actualizada |
| GET | `/api/catalogos` | `estados`, recursos (ID/nombre), roles (ID/descripción) |
| GET | `/api/proyectos` | Array; filtros opcionales `estado` y `responsable` (ID numérico; si no es numérico, 400) |
| GET | `/api/proyectos/<id>` | `proyecto`, `consumos`, `por_recurso`, `por_rol` |
| POST | `/api/proyectos` | Crear, devuelve proyecto (201) |
| PUT | `/api/proyectos/<id>` | Reemplazar campos editables, devuelve proyecto (200) |
| DELETE | `/api/proyectos/<id>` | Eliminar (204) |
| GET | `/api/proyectos/<id>/tareas` | Tareas del proyecto, ordenadas por fecha de inicio (todos los usuarios) |
| POST | `/api/proyectos/<id>/tareas` | Crear tarea (201); responsable del proyecto o administrador |
| GET | `/api/tareas/<id>` | Tarea individual |
| PUT / DELETE | `/api/tareas/<id>` | Actualizar (200) o eliminar (204); responsable del proyecto o administrador |
| GET | `/api/consumos` | Array de consumos con nombres de proyecto/recurso/rol |
| GET | `/api/consumos/<id>` | Consumo individual |
| POST / PUT / DELETE | `/api/consumos`, `/api/consumos/<id>` | Crear (201), actualizar (200), eliminar (204) |
| GET | `/api/recursos`, `/api/recursos/<id>` | Lista o recurso sin hash; solo administrador |
| POST / PUT / DELETE | `/api/recursos`, `/api/recursos/<id>` | Crear (201), actualizar (200), eliminar (204); solo administrador |
| GET | `/api/roles`, `/api/roles/<id>` | Lista o rol; solo administrador |
| POST / PUT / DELETE | `/api/roles`, `/api/roles/<id>` | Crear (201), actualizar (200), eliminar (204); solo administrador |

POST usa la colección; PUT y DELETE usan un ID. PUT recibe todos los campos editables; no es una actualización parcial.

## Cuerpos de escritura

- Proyecto: `proyecto_nombre`, `fecha_inicio`, `fecha_fin`, `horas_requeridas`, `owner_id`, `proyect_status`, `porcentaje_avance`. El responsable no administrador no puede cambiar owner_id; se conserva el actual.
- Consumo: `proyecto_id`, `recurso_id`, `fecha_inicio`, `fecha_fin`, `horas_consumidas`, `tarea`, `rol_id`. Para un usuario común, recurso_id siempre se obtiene de la sesión, ignorando el valor enviado.
- Recurso: `recurso_nombre`, `es_admin` (booleano, por defecto false), `password`. Al editar, omitir password o enviar cadena vacía conserva la contraseña; proporcionar una nueva exige cambio en el próximo acceso.
- Rol: `rol_descripcion`.
- Tarea: `tarea_nombre`, `fecha_inicio`, `fecha_fin`, `porcentaje_avance` y `recurso_id` opcional (responsable de la tarea; `null` o cadena vacía = sin asignar). El proyecto sale de la ruta al crear y no cambia al editar.

Fechas ISO `YYYY-MM-DD`. Horas positivas finitas. Avance 0–100. Los números e IDs pueden enviarse como números JSON o cadenas numéricas; no se aceptan booleanos, objetos o listas como valores numéricos. Textos obligatorios no pueden estar vacíos.

Las lecturas de proyectos incluyen `responsable`, `horas_consumidas`, `saldo`, `exceso` y `porcentaje_consumo`. El detalle agrega `por_recurso` y `por_rol` como objetos de nombre → horas. No se modifica porcentaje_avance al registrar horas.

## Errores

Formato uniforme: `{ "error": { "code": "validation_error", "message": "Mensaje legible" } }`.

- 400: validación (`validation_error`, con mensaje en español), JSON malformado o CSRF inválido (`csrf_invalid`). Un JSON malformado se rechaza antes de verificar la sesión.
- 401: sesión ausente (`unauthorized`) o credenciales incorrectas (`invalid_credentials`).
- 403: permisos insuficientes, o cambio inicial pendiente (`password_change_required`).
- 404: registro o ruta inexistente, incluido un ID de ruta no numérico (`/api/roles/abc`). 405: método no permitido.
- 409: duplicados/referencias (`conflict`) o protección del último administrador (`last_admin`).
- 413: solicitud demasiado grande; límite 1 MiB. 415: falta Content-Type JSON.
- 500: error interno no previsto (`http_500`), siempre como JSON y sin detalles internos.
- 502/503: el proxy (Caddy o Vite) no puede conectar con la API. Esta respuesta no la genera la API y puede no ser JSON; en ese caso el frontend muestra el mensaje genérico "No se pudo completar la solicitud."

Orden de verificación en cada endpoint protegido: 401 sin sesión → 403 `password_change_required` → 400 `csrf_invalid` → 415 sin JSON → 400 si el cuerpo no es un objeto → 403 por permisos del recurso → 400 por validación de campos. Así, un usuario sin permisos recibe 403 aunque los datos enviados sean inválidos.

Los errores no generan reintentos automáticos de escritura. El frontend conserva el formulario para corregirlo, informa desconexiones y redirige al login o al cambio de contraseña según corresponda.

## Tareas (Gantt)

Cada proyecto tiene tareas planificadas que el frontend muestra como diagrama de Gantt en el detalle del proyecto. Las lecturas devuelven `tarea_id`, `proyecto_id`, `tarea_nombre`, `fecha_inicio`, `fecha_fin`, `porcentaje_avance`, `recurso_id` y `recurso_nombre` (null si no tiene responsable).

- Las fechas de la tarea deben estar dentro de las del proyecto; si no, 400 con el rango del proyecto en el mensaje.
- Un `PUT /api/proyectos/<id>` que deja tareas fuera del nuevo rango devuelve 400 ("Hay N tarea(s) fuera de las nuevas fechas del proyecto…").
- Eliminar un proyecto con tareas devuelve 409 `conflict`: primero hay que eliminar sus tareas.
- Los permisos (responsable del proyecto o administrador) se verifican antes de validar el cuerpo, igual que en el resto de la API. Guardar una tarea y cambiar las fechas del proyecto bloquean la fila del proyecto, para que un pedido concurrente no deje tareas afuera.
- El avance de las tareas no modifica el `porcentaje_avance` del proyecto, que sigue siendo manual.

## Email de recursos

POST y PUT de recursos aceptan `email` opcional (texto o null). Vacío o espacios se normalizan a null; se recortan espacios externos. Un valor inválido devuelve 400 con un mensaje en español. PUT sin email lo deja en null, como reemplazo completo. Los recursos y la sesión incluyen email; los catálogos generales siguen mostrando solo ID y nombre. No hay restricción de unicidad ni verificación de entrega de correo.
