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

| POST | `/api/carga-masiva/<entidad>` | Carga masiva multipart (vista previa o `confirmar=true`); ver "Carga masiva" |
| GET | `/api/carga-masiva/<entidad>/plantilla.csv` | Plantilla CSV de la entidad |

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

## Reporte del proyecto (dashboard)

`GET /api/proyectos/<id>/reporte?periodo=semana|mes` (cualquier usuario autenticado; `periodo` inválido → 400, proyecto inexistente → 404). Devuelve en un solo pedido todo lo que muestra el dashboard `/proyectos/<id>/dashboard`:

- `fecha_corte`: "hoy" para los cálculos (zona Buenos Aires); el frontend no usa su propio reloj.
- `salud`: porcentajes de tiempo, consumo y avance; `horas_ganadas` (avance × horas requeridas); `indice_eficiencia` (ganadas / consumidas) e `indice_cronograma` (avance / tiempo), con su estado `bien` (≥ 1), `atencion` (≥ 0,85) o `critico`. Los índices son `null` si el denominador es 0.
- `periodos`: horas por semana (desde el lunes) o mes, con desglose `por_rol` y `por_recurso`; incluye períodos sin horas entre el primero y el último.
- `ritmo`: horas por semana de los últimos 28 días (÷ 4), promedio histórico y necesario para terminar a tiempo (`null` si venció o no queda saldo).
- `ejecucion`: primer y último consumo, desvío de inicio en días, horas fuera del plazo planificado y días con actividad.
- `tareas`: contadores, tareas vencidas y atrasadas sin iniciar, y avance planificado vs. real ponderado por duración.
- `distribucion`: horas y porcentaje por recurso, por rol y por actividad (top 8 por el texto de `consumo.tarea` + "Otras").

Las horas de cada consumo se reparten en partes iguales entre sus fechas (ambas incluidas), la misma regla del gráfico de horas acumuladas. No hay horas por tarea del Gantt (el vínculo consumo↔tarea se descartó). Los umbrales del semáforo son constantes de `backend/pulso/reports.py`.

## Carga masiva

Carga de registros desde un archivo, siempre en dos pasos: vista previa y confirmación. No guarda nada entre ambos pasos: para confirmar se vuelve a subir el mismo archivo con `confirmar=true`.

- `POST /api/carga-masiva/<entidad>?confirmar=false|true`: `multipart/form-data` con el campo `archivo`. `<entidad>` es `roles`, `recursos`, `proyectos`, `tareas` o `consumos` (otro valor → 404). Es la **única excepción** a "toda mutación es JSON": no exige `Content-Type: application/json` ni cuerpo objeto, pero sigue exigiendo sesión (401), cambio de contraseña resuelto (403) y CSRF (`X-CSRF-Token`).
- `GET /api/carga-masiva/<entidad>/plantilla.csv`: plantilla CSV (UTF-8 con BOM) con los encabezados y una fila de ejemplo.

Formatos: `.csv`, `.txt` (delimitador detectado entre `,` `;` tabulación y `|`; UTF-8 o cp1252) y `.xlsx` (solo la primera hoja). La primera fila no vacía son los encabezados, que no distinguen mayúsculas, tildes ni espacios; se admiten alias (por ejemplo `nombre`, `inicio`, `fin`, `horas`, `estado`). Las columnas desconocidas se ignoran con una advertencia. Fechas ISO `YYYY-MM-DD`, `dd/mm/aaaa` o fechas de Excel; números con coma o punto decimal; booleanos `sí/no`, `true/false`, `verdadero/falso`, `1/0`.

Límites: 5 MiB por archivo (413 `http_413`) y 200 filas para `recursos`, 5000 para el resto (400 `archivo_demasiado_grande`). La respuesta informa como máximo 500 errores y 500 advertencias (`errores_total` es el total real).

Respuesta (`CargaResultado`, 200): `entidad`, `total` (filas leídas), `validas`, `errores_total`, `errores` y `advertencias` (listas de `{fila, campo, mensaje}`, `fila` es el número de línea del archivo), `creadas` y `confirmada`.

- Sin `confirmar` (vista previa) no se escribe nada.
- Con `confirmar=true` la carga es todo o nada: si hay algún error no se crea ninguna fila y la respuesta es **200 con `confirmada: false`** (no un 4xx); si no hay errores se crean todas en una transacción y `confirmada` es `true`.

Errores de archivo (400): `formato_no_soportado`, `archivo_invalido` (vacío, sin filas, xlsx corrupto, columnas repetidas, falta el campo `archivo`) y `columnas_faltantes`. Los permisos de la entidad se verifican antes de leer el archivo (403 antes que 400).

Permisos: `roles`, `recursos` y `proyectos` solo administrador. `tareas`: administrador o responsable del proyecto de cada fila (se comprueba fila por fila). `consumos`: cualquier usuario, solo consumos propios (el administrador puede indicar otro recurso).

Columnas por entidad (obligatorias en negrita; «a | b» significa que alcanza con una):

| Entidad | Columnas |
|---|---|
| `roles` | **`rol_descripcion`** |
| `recursos` | **`recurso_nombre`**, **`password`** (mínimo 8), `email`, `es_admin`; los usuarios creados deben cambiar la contraseña al ingresar |
| `proyectos` | **`proyecto_nombre`**, **`fecha_inicio`**, **`fecha_fin`**, **`horas_requeridas`**, **`owner` \| `owner_id`**, **`proyect_status`**, `porcentaje_avance` |
| `tareas` | **`proyecto` \| `proyecto_id`**, **`tarea_nombre`**, **`fecha_inicio`**, **`fecha_fin`**, `porcentaje_avance`, `recurso` \| `recurso_id` |
| `consumos` | **`proyecto` \| `proyecto_id`**, **`rol` \| `rol_id`**, **`fecha_inicio`**, **`fecha_fin`**, **`horas_consumidas`**, **`tarea`**, `recurso` \| `recurso_id` (obligatorio para administradores) |

Resolución por nombre: `owner`, `recurso`, `proyecto` y `rol` se buscan por nombre sin distinguir mayúsculas; los `*_id` por ID. Si vienen ambos, deben coincidir. Un nombre inexistente o un proyecto con nombre repetido (ambiguo) es un error de esa fila: se debe usar `proyecto_id`. Las reglas de validación son las de los endpoints individuales (fechas dentro del proyecto para tareas, 12 h por día para consumos, etc.).

Efectos: al confirmar `consumos` se envía un correo resumen por proyecto (al responsable y a los recursos con email) y, si el proyecto supera sus horas requeridas con esa carga, la alerta de horas excedidas al responsable. Los correos se envían en segundo plano.

Límites conocidos:

- En desarrollo o contra uvicorn directo, una subida multipart en chunks sin `Content-Length` la acumula Starlette antes de autenticar y el tope de tamaño se aplica después; en producción lo evita Caddy (`max_size 6MB` en `/api/carga-masiva/*`).
- Los consumos idénticos a uno existente solo generan una advertencia; se cargan igual.
- Los datos que sigan a más de 10 000 filas vacías consecutivas en una hoja se ignoran.

## Email de recursos

POST y PUT de recursos aceptan `email` opcional (texto o null). Vacío o espacios se normalizan a null; se recortan espacios externos. Un valor inválido devuelve 400 con un mensaje en español. PUT sin email lo deja en null, como reemplazo completo. Los recursos y la sesión incluyen email; los catálogos generales siguen mostrando solo ID y nombre. No hay restricción de unicidad ni verificación de entrega de correo.
