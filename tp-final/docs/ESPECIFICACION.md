# Especificación funcional

Aplicación web de seguimiento de proyectos, en español, para un equipo chico. Se despliega en un servidor propio con HTTPS. El frontend usa Vue 3 + TypeScript (estilos propios sobre Bootstrap) y el backend es una API JSON en FastAPI con PostgreSQL.

## Entidades

- Proyecto: proyecto_id, proyecto_nombre, fecha_inicio, fecha_fin, horas_requeridas, owner_id, proyect_status, porcentaje_avance.
- Recurso/usuario: recurso_id, recurso_nombre único (login), password (hash), es_admin y debe_cambiar_password.
- Consumo: consumo_id, proyecto_id, recurso_id, fecha_inicio, fecha_fin, horas_consumidas, tarea y rol_id.
- Rol: rol_id y rol_descripcion única. Es una función laboral, no un permiso.
- Tarea: tarea_id, proyecto_id, tarea_nombre, fecha_inicio, fecha_fin, porcentaje_avance y recurso_id opcional (responsable de la tarea). Es la planificación del proyecto.

El responsable referencia un recurso registrado. Las referencias se protegen con claves foráneas y eliminación restrictiva. Se conserva el nombre `proyect_status` solicitado. Estados: Pendiente, En curso, Pausado y Finalizado.

## Reglas de negocio

El avance real es manual de 0 a 100, independiente del estado y del consumo. Horas requeridas y consumidas: positivas y finitas. Fechas obligatorias, inicio no posterior al fin. Se permiten horas por encima de la estimación y fuera del período previsto. Saldo = requeridas − consumidas; exceso = máximo(consumidas − requeridas, 0); porcentaje de consumo = consumidas / requeridas × 100. Los totales se calculan desde los consumos actuales.

Las tareas deben quedar dentro de las fechas de su proyecto, y el rango de un proyecto no puede achicarse dejando tareas afuera. Un proyecto con tareas no puede eliminarse. El avance de las tareas (0 a 100) es independiente del avance manual del proyecto. Una tarea está atrasada si su fecha de fin ya pasó y no llegó al 100 %.

## Acceso

Todos los usuarios autenticados consultan proyectos y consumos; los usuarios comunes crean, editan y eliminan consumos propios. El responsable edita su proyecto salvo la asignación del responsable, y planifica sus tareas (crear, editar, reprogramar y eliminar). El administrador administra todo, incluidos recursos y roles, creación/eliminación de proyectos y reasignaciones. Debe quedar al menos un administrador. Se verifican permisos en el servidor.

La inicialización de una base vacía crea admin / Proyecto1 y exige cambiar esa contraseña. Nuevos usuarios y contraseñas restablecidas también requieren cambio. La inicialización no sobrescribe cuentas. Contraseñas con hash argon2id y mínimo de 8 caracteres para las nuevas. Los hashes scrypt de la versión anterior se aceptan y se actualizan en el siguiente ingreso. Cambiar o restablecer una contraseña cierra las otras sesiones de la cuenta. Todas las mutaciones requieren JSON y CSRF: POST para altas, PUT para actualizaciones y DELETE para bajas. Todavía no hay recuperación por correo. El envío de alertas por correo está previsto para una etapa posterior (Fase 5).

## Interfaz y aceptación

Tablero con filtros de estado/responsable, tarjetas, horas y avance real; detalle con planificación (diagrama de Gantt de las tareas, con escala día/semana/mes; el responsable o un administrador arrastra las barras para cambiar fechas o avance), consumos y totales por recurso/rol. Formularios con errores comprensibles y preservación de entradas no sensibles. Diseño adaptable a móvil. Aceptación: CRUD, login/logout, permisos directos, CSRF, integridad, porcentajes límite, recálculo, persistencia e inicialización repetible.

## Separación tecnológica

El frontend compilado consume exclusivamente la API JSON, mediante un cliente tipado que se genera desde el esquema OpenAPI. La API verifica autenticación, permisos y validaciones. Las sesiones se guardan en la base de datos, y los cambios de esquema se aplican con migraciones Alembic. Se conservan los nombres de tablas y columnas originales, y los datos de la versión SQLite se importan con `python -m pulso.cli import-sqlite`. El contrato HTTP está en docs/API.md. No se utilizan plantillas Jinja.

## Despliegue

Caddy sirve el frontend, obtiene el certificado HTTPS y reenvía `/api` a la API. PostgreSQL persiste los datos, con un backup diario. Todo se levanta con Docker Compose (`compose.prod.yaml`). Los secretos (la contraseña de la base) se leen de variables de entorno y no se guardan en Git.

## Próximas funcionalidades (Fase 5, pendiente)

- Cargas masivas por CSV, con vista previa de errores por fila.
- Alertas por correo: presupuesto excedido, proyecto vencido y días sin carga de horas.

El reporting ya está implementado como dashboard por proyecto (`/proyectos/<id>/dashboard`): salud y desvíos (tiempo vs. horas vs. avance, con índices de eficiencia y de cronograma), horas por semana o mes apiladas por rol o recurso, ritmo y proyección de la fecha de fin, ejecución real vs. plan, salud de las tareas y distribución de horas. Ver `docs/API.md`.

La planificación Gantt ya está implementada (tareas por proyecto). Por decisión del usuario quedaron fuera de alcance las dependencias entre tareas y el vínculo de consumos con tareas.

El recurso incluye `email` opcional: si se proporciona, debe tener formato usuario@dominio.extension. Las cuentas existentes conservan email null hasta que se complete.
