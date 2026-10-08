# Archivos de ejemplo para la carga masiva

Se cargan desde **Carga masiva** (`/carga-masiva`) como administrador, **en este orden** (cada archivo depende del anterior):

| Orden | Archivo | Entidad | Formato | Contenido |
|---|---|---|---|---|
| 1 | `roles.csv` | Roles | CSV (coma) | 4 roles |
| 2 | `recursos.txt` | Recursos | TXT (tabulador) | 3 usuarios, contraseña inicial `Cambiar1234` (deben cambiarla al ingresar) |
| 3 | `proyectos.xlsx` | Proyectos | Excel | 3 proyectos con responsables `lucia`, `martin` y `sofia` |
| 4 | `tareas.csv` | Tareas | CSV (punto y coma, fechas `DD/MM/AAAA`) | 6 tareas dentro de las fechas de cada proyecto |
| 5 | `consumos.xlsx` | Consumos | Excel | 10 consumos de horas (como administrador hay que indicar el recurso en cada fila) |

Los cinco archivos se verificaron cargándolos en este orden sobre una base vacía de roles, recursos y proyectos. Primero se ve la vista previa y recién después se confirma. Si un rol o usuario ya existe en la base, la vista previa lo marca como error de fila (por ejemplo, `Analista`); borrá esa fila del archivo o cambiale el nombre.
