# Historial de desarrollo de Pulso

Este documento resume los pasos seguidos en la conversación para crear la aplicación de seguimiento de proyectos y luego separar su frontend del backend. Es una reconstrucción del proceso y de las decisiones tomadas, no una transcripción literal ni un historial de commits.

## 1. Solicitud inicial

Se solicitó una aplicación web para registrar el avance en la ejecución de proyectos, con SQLite como base de datos del backend y cuatro tablas:

| Tabla | Campos solicitados inicialmente |
|---|---|
| proyecto | proyecto_id, proyecto_nombre, fecha_inicio, fecha_fin, horas_requeridas, owner_id, proyect_status |
| recurso | recurso_id, recurso_nombre |
| consumo | proyecto_id, recurso_id, fecha_inicio, fecha_fin, horas_consumidas, tarea, rol_id |
| rol | rol_id, rol_descripcion |

## 2. Revisión del repositorio

Antes de definir la implementación se inspeccionó el directorio del trabajo práctico. Solo contenía un README; todavía no había código de aplicación.

El README pedía una aplicación con interfaz, servidor y persistencia, además de documentación de la especificación, el plan y las decisiones. También solicitaba evidencia del proceso mediante ramas, commits y pull requests.

Se verificó que la raíz Git estaba en el directorio padre de `tp-final`.

## 3. Aclaración de requisitos con el usuario

La conversación permitió resolver las siguientes decisiones:

| Tema | Decisión acordada |
|---|---|
| Responsable | `owner_id` referencia un `recurso_id` registrado. |
| Usuarios | Cada recurso también es un usuario del sistema. |
| Acceso | Login mediante nombre de usuario y contraseña. |
| Administrador | Cuenta inicial `admin`, con contraseña inicial `Proyecto1` y acceso completo. |
| Contraseñas | Almacenamiento mediante hash seguro, en lugar de texto plano o cifrado reversible. |
| Seguimiento | Mostrar horas consumidas frente a horas requeridas. |
| Avance real | Agregar `porcentaje_avance`, cargado manualmente entre 0 y 100. |
| Roles | Representan la función desempeñada en un consumo, no los permisos del sistema. |
| Tecnología inicial | Python, Flask, plantillas HTML y Bootstrap, con SQLite. |

Se distinguió expresamente el consumo de horas del avance real: gastar el 80 % de las horas previstas no demuestra que se haya completado el 80 % del trabajo.

## 4. Definición de permisos

Se eligió un esquema según responsabilidad:

- Todos los usuarios autenticados pueden consultar proyectos y consumos.
- Los usuarios comunes pueden crear, editar y eliminar sus propios consumos.
- El responsable puede editar los datos, el estado y el avance de su proyecto.
- El administrador puede gestionar todos los registros, crear y eliminar proyectos, reasignar responsables y administrar recursos y roles.
- La asignación del responsable queda reservada al administrador.
- El sistema debe conservar al menos un administrador.

Los permisos se verifican en el servidor, además de controlar los botones visibles en la interfaz.

## 5. Elaboración y aprobación del plan

Se presentó un plan antes de escribir la aplicación. El usuario pidió explícitamente implementarlo.

El plan incluyó estas ampliaciones al modelo original:

- `consumo_id` como identificador propio de cada registro de horas.
- `password` y `es_admin` en recurso.
- Un indicador `debe_cambiar_password` para exigir el cambio de contraseña inicial o restablecida.
- `porcentaje_avance` en proyecto.
- Claves foráneas para relacionar proyectos, recursos, consumos y roles.

También se definieron los estados de proyecto: pendiente, en curso, pausado y finalizado. Se conservó el nombre de campo `proyect_status` solicitado.

La primera entrega se limitó a ejecución local, sin publicación en Internet, recuperación de contraseña por correo ni gestión de tareas como entidad independiente.

## 6. Implementación inicial con Flask y plantillas

Se construyó la primera versión bajo el nombre **Pulso**:

1. Fábrica de aplicación Flask y módulos separados para autenticación, proyectos, recursos, roles y consumos.
2. Esquema SQLite y conexión por solicitud con claves foráneas activadas.
3. Comando `init-db` para crear la base y la cuenta inicial sin sobrescribir usuarios existentes.
4. Login, logout, cambio de contraseña y protección CSRF en formularios.
5. Pantallas de altas, consultas, modificaciones y bajas.
6. Tablero con filtros por estado y responsable.
7. Detalle de proyecto con consumos y totales por recurso y rol.
8. Interfaz en español, con Bootstrap y CSS adaptable a escritorio y móvil.

La base se ubicó en `instance/proyectos.sqlite`, fuera del control de versiones. La clave de sesión se configuró mediante `SECRET_KEY`.

## 7. Reglas de validación e integridad

Se implementaron las siguientes reglas:

- Nombres y tareas obligatorios.
- Horas requeridas y consumidas positivas y finitas.
- Fechas válidas, con inicio no posterior al fin.
- Avance manual entre 0 y 100.
- Bloqueo de eliminaciones cuando existen referencias asociadas.
- Protección contra la eliminación o degradación del último administrador.
- Identificadores autoincrementales para evitar reutilizar el ID de una cuenta eliminada.

Se permitieron consumos fuera del período previsto y por encima de las horas estimadas para registrar desvíos reales.

Los indicadores se calcularon así:

```text
Saldo = horas requeridas − horas consumidas
Exceso = máximo(horas consumidas − horas requeridas, 0)
Porcentaje de consumo = horas consumidas / horas requeridas × 100
```

El porcentaje de avance real y el estado permanecieron independientes de esos cálculos.

## 8. Pruebas y correcciones de la primera versión

Se escribieron pruebas con bases SQLite temporales para autenticación, permisos, CRUD, referencias, validaciones, totales y persistencia.

La primera ejecución detectó un error en `init-db`: faltaba el contexto de aplicación de Flask. Se corrigió incorporando `with_appcontext` y se volvió a verificar el comando.

También se comprobó que:

- Un usuario no pueda modificar consumos ajenos mediante solicitudes directas.
- Un formulario modificado no permita atribuir consumos a otro recurso.
- Un responsable no pueda reasignar su proyecto.
- Cambiar consumos actualice los totales sin alterar el avance manual.
- Repetir la inicialización no restablezca contraseñas.
- Una cuenta nueva no reutilice el ID de una cuenta eliminada.

La versión inicial terminó con **49 pruebas automatizadas aprobadas**.

## 9. Revisión visual inicial

Se inició una instancia de prueba con una base temporal, separada de la base real.

En el navegador se verificaron el login, el tablero, la creación de un proyecto y la carga de un consumo de 12,5 horas. Se comprobaron los totales por recurso y rol y la conservación del avance manual.

Se revisó el diseño a 390 × 844 píxeles. La tabla comprimía demasiado las palabras, por lo que se agregó un ancho mínimo con desplazamiento horizontal.

Después se inició la aplicación real en el puerto 5000, con la base inicial limpia. El usuario completó el cambio de contraseña inicial.

## 10. Restricción encontrada al trabajar con Git

Se intentó crear la rama `codex/seguimiento-proyectos`, pero los metadatos Git estaban en el directorio padre, fuera del espacio habilitado para escritura.

La solicitud de autorización para crear la rama fue rechazada. Por ese motivo, el asistente continuó trabajando en los archivos de la aplicación, pero no creó la rama, commits ni un PR. Esto no implica que el usuario no haya realizado operaciones Git por su cuenta posteriormente.

## 11. Solicitud de cambio tecnológico

Después de la primera entrega, el usuario solicitó:

> necesito cambiar la tecnologia, separar en frontend con html, javascript y css y backend con api

Se decidió conservar Python, Flask, SQLite y las reglas funcionales, y cambiar la forma en que se comunican la interfaz y el servidor.

No fue necesario modificar el esquema de la base ni restablecer usuarios o contraseñas.

## 12. Conversión del backend a API JSON

Los módulos de Flask se adaptaron para exponer rutas bajo `/api`:

- Sesión actual, login, logout y cambio de contraseña.
- Consulta de catálogos para selectores y filtros.
- Gestión de proyectos, consumos, recursos y roles.
- Totales y resúmenes calculados por el backend.

Se reemplazaron los formularios HTML y las redirecciones del servidor por un contrato HTTP:

| Método | Uso |
|---|---|
| GET | Consultar datos y sesión. |
| POST | Crear registros, iniciar sesión y cerrarla. |
| PUT | Actualizar registros y cambiar contraseña. |
| DELETE | Eliminar registros. |

La API devuelve JSON, con errores estructurados y códigos HTTP. Las eliminaciones exitosas responden 204 sin cuerpo.

Se conservaron las cookies de sesión HttpOnly y la protección CSRF. El frontend obtiene el token desde `/api/session` y lo envía en el encabezado `X-CSRF-Token` al modificar datos. Las respuestas nunca incluyen hashes de contraseñas.

## 13. Creación del frontend independiente

Se creó el directorio `frontend/` con los siguientes componentes:

| Archivo | Responsabilidad |
|---|---|
| `index.html` | Estructura HTML inicial. |
| `app.js` | Navegación, pantallas, formularios y eventos. |
| `api.js` | Solicitudes con `fetch`, JSON, cookies, CSRF y manejo de errores. |
| `ui.js` | Componentes de presentación y escape de contenido. |
| `styles.css` | Estilos de la aplicación. |
| `server.py` | Servidor local de archivos estáticos y proxy hacia la API. |

Se retiraron las plantillas Jinja y se trasladaron los estilos al frontend. Los módulos JavaScript no requieren compilación para ejecutar la aplicación.

Los formularios conservaron sus datos ante errores de validación. Se incorporaron mensajes de carga y fallos de conexión, sin reintentar automáticamente operaciones de escritura.

## 14. Separación de procesos y puertos

La arquitectura pasó a ser:

```text
Navegador: HTML + JavaScript + CSS
                  |
                  | fetch('/api/...')
                  v
Frontend y proxy local: puerto 8000
                  |
                  | solicitudes JSON
                  v
API Flask: puerto 5000
                  |
                  v
SQLite: instance/proyectos.sqlite
```

El proxy del frontend reenvía `/api/*` al backend. Esto permite utilizar un único origen desde el navegador para cookies y CSRF, sin habilitar CORS amplio. El proxy no contiene reglas de negocio ni accede a SQLite.

Para las pruebas visuales se utilizaron otros puertos y una base temporal.

## 15. Pruebas de la arquitectura separada

Las pruebas de la primera versión se adaptaron al contrato JSON y se agregaron verificaciones específicas del frontend y el proxy.

| Grupo | Resultado registrado |
|---|---|
| API Flask | 66 pruebas aprobadas. |
| Servidor estático y proxy | 2 pruebas aprobadas. |
| Cliente JavaScript | 2 pruebas aprobadas. |

Estos resultados reemplazan la suite inicial; no deben sumarse a las 49 pruebas de la primera versión.

Se comprobaron, entre otros casos:

- JSON inválido, tipos de datos incorrectos y Content-Type inadecuado.
- CSRF en POST, PUT y DELETE.
- Ausencia de hashes en las respuestas.
- Permisos y reglas funcionales existentes.
- Login con cookies a través del proxy mediante llamadas HTTP reales.
- Respuesta comprensible cuando el backend no está disponible.
- Escape de contenido en HTML generado por JavaScript.
- Renovación del token CSRF y manejo de respuestas 204.

También se verificaron la compilación de Python, la sintaxis JavaScript y los cambios con `git diff --check`.

## 16. Revisión visual de la nueva versión

Se recorrió la interfaz separada en el navegador:

1. Login y carga del tablero desde la API.
2. Creación de un proyecto con 20 horas requeridas y 40 % de avance manual.
3. Intento de registrar cero horas: apareció el error del backend y se conservaron los datos del formulario.
4. Registro de 25,5 horas fuera de las fechas previstas: se mostraron 5,5 horas de exceso, sin cambiar el avance manual.
5. Recarga de la URL de detalle para comprobar navegación y sesión.
6. Creación y edición de un rol.
7. Aplicación de un filtro sin resultados y limpieza del filtro.
8. Revisión móvil a 390 × 844 píxeles, sin desbordamiento horizontal de la página.
9. Cierre de sesión y retorno al formulario de ingreso.

Los datos de este recorrido se mantuvieron en la base temporal.

## 17. Puesta en marcha y documentación

Se detuvo el servidor de la primera versión y se iniciaron los dos procesos de la nueva arquitectura. La base existente se conservó. Al generar una nueva clave de sesión durante el reinicio fue necesario volver a iniciar sesión con la contraseña vigente.

Se actualizaron o crearon los siguientes documentos:

- [README](../README.md): instalación, ejecución, arquitectura y permisos.
- [Especificación](ESPECIFICACION.md): entidades y reglas funcionales.
- [Plan](PLAN.md): pasos de la separación tecnológica.
- [Contrato de API](API.md): endpoints, cuerpos JSON y errores.
- [Validación](VALIDACION.md): pruebas y recorridos verificados.
- Este historial: secuencia de decisiones y acciones de la conversación.

La última acción de navegación para dejar abierta la aplicación real en el puerto 8000 fue interrumpida. La conversación sí registra el inicio de ambos servidores y la revisión de la versión separada en el entorno de prueba. Su ejecución actual debe comprobarse al retomar el proyecto.

## 18. Resultado del proceso

La aplicación evolucionó de una solución Flask con páginas renderizadas en el servidor a una arquitectura con frontend HTML/JavaScript/CSS y backend API Flask, manteniendo SQLite y las reglas de negocio acordadas.

El proceso combinó aclaración de requisitos, planificación aprobada por el usuario, implementación, pruebas automatizadas, revisión visual y documentación. La solicitud posterior de separación tecnológica se implementó conservando la base existente.

## 19. Replataforma FastAPI + Vue + PostgreSQL (2026-09-23)

La etapa siguiente se registra prompt por prompt, con cada acción, en [prompts.md](../prompts.md) (en la raíz de `tp-final/`). En resumen:

- Se revisó la arquitectura con el objetivo de un despliegue real para un equipo chico.
- Se eligieron FastAPI, Vue 3 + TypeScript, PostgreSQL, sesión por cookie con CSRF, y Docker Compose con Caddy.
- Se ejecutó en fases, con un commit por fase en la rama `replatform-fastapi-vue`: fundamentos, paridad del backend, paridad del frontend, despliegue y documentación.
- Las funcionalidades nuevas del roadmap (Fase 5) quedaron para más adelante.

## 20. Planificación Gantt (2026-09-30)

Registrada prompt por prompt en [prompts.md](../prompts.md) (Prompts 5 a 11), en la rama `feat-gantt-chart`. En resumen:

- Se planificó en entregas: vista general, tareas, dependencias, vínculo consumo↔tarea y documentación.
- La vista general de todos los proyectos se implementó y el usuario la descartó: el Gantt se accede desde cada proyecto y muestra sus tareas.
- Se implementaron las tareas (tabla `tarea`, API, formulario y diagrama con frappe-gantt que se puede arrastrar), con sus reglas de fechas y de borrado.
- Las dependencias y el vínculo con consumos se descartaron por exceder el alcance de la herramienta.
