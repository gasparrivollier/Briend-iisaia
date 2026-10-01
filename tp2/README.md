# Contrato de API de Pulso

## Qué construí

Construí un contrato de API en OpenAPI 3.0.3 para Pulso, un sistema de seguimiento de proyectos y horas de trabajo. El entregable es [contrato-ejercicio.yaml](contrato-ejercicio.yaml).

Definí dos recursos relacionados: **proyectos** y **dedicaciones**. Cada dedicación pertenece a un proyecto y registra una persona, una fecha, una cantidad de horas y una tarea.

| Método | Ruta | Operación |
|---|---|---|
| GET | `/proyectos` | Listar proyectos |
| POST | `/proyectos` | Crear un proyecto |
| GET | `/proyectos/{proyecto_id}/dedicaciones` | Listar las dedicaciones de un proyecto |
| POST | `/proyectos/{proyecto_id}/dedicaciones` | Registrar una dedicación |
| DELETE | `/proyectos/{proyecto_id}/dedicaciones/{dedicacion_id}` | Eliminar una dedicación |

Documenté los cuerpos de entrada, los schemas de respuesta y los códigos HTTP: 200 para lecturas, 201 para creaciones, 204 para una eliminación exitosa sin cuerpo, 400 para datos inválidos y 404 para recursos inexistentes o ajenos al proyecto indicado.

## Cómo se ejecuta

Este entregable no requiere ejecutar un servidor: es un contrato, no una implementación de la API.

Para consultarlo, se puede abrir `contrato-ejercicio.yaml` en un editor de texto o cargarlo en un visor compatible con OpenAPI, como Swagger Editor. El visor permite explorar las operaciones, los campos obligatorios y las respuestas documentadas. Ejecutar solicitudes reales requiere implementar y configurar un servidor que cumpla este contrato.

La propuesta es independiente de la API existente de Pulso. Sus rutas no deben interpretarse como endpoints ya disponibles en el backend actual.

## Qué me propuse

Me propuse describir una API pequeña y comprensible que cumpliera los cuatro requisitos de la consigna:

- Incluir los métodos GET, POST y DELETE.
- Mostrar una jerarquía de recursos en las rutas.
- Documentar al menos un error 400 o 404; incluí ambos.
- Definir schemas con `type`, `required` y `format` donde corresponde.

El alcance fue elaborar el contrato, sin implementar nuevas funcionalidades.

## Qué decidí yo

Elegí el dominio de Pulso para aprovechar el contexto del proyecto existente. Usé proyectos como recurso contenedor y dedicaciones como recurso dependiente.

Decidí que los identificadores fueran enteros positivos asignados por el servidor, que las fechas usaran el formato `YYYY-MM-DD` y que cada dedicación registrara más de cero y hasta 24 horas. Los textos obligatorios no pueden estar vacíos ni contener únicamente espacios.

El identificador del proyecto se obtiene de la ruta al crear una dedicación. También definí que intentar eliminar una dedicación perteneciente a otro proyecto devuelva 404 y que repetir una eliminación exitosa produzca ese mismo código.

Para mantener el ejercicio acotado, dejé autenticación y paginación fuera del contrato propuesto.

## Qué salió mal y cómo lo corregí

Al revisar el proyecto, detecté que las rutas actuales de proyectos y consumos no expresaban la jerarquía solicitada por el ejercicio. Resolví esa diferencia mediante una propuesta independiente con la ruta `/proyectos/{proyecto_id}/dedicaciones`, sin cambiar la implementación ni el contrato utilizado por el frontend.

Además, el entorno no tenía instalado un validador completo de OpenAPI. Como verificación parcial, comprobé que el archivo fuera YAML válido, que sus referencias internas se resolvieran, que las cinco operaciones tuvieran identificadores únicos y que los schemas de objetos declararan `type` y `required`. Esas comprobaciones pasaron; queda pendiente la validación integral contra la especificación OpenAPI.
