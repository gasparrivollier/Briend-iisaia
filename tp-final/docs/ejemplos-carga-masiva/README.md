# Archivos de ejemplo para la carga masiva

Se cargan desde **Carga masiva** (`/carga-masiva`) como administrador, **en este orden** (cada archivo depende del anterior):

| Orden | Archivo | Entidad | Formato | Contenido |
|---|---|---|---|---|
| 1 | `roles.csv` | Roles | CSV (coma) | 4 roles |
| 2 | `recursos.txt` | Recursos | TXT (tabulador) | 3 usuarios, contraseña inicial `Cambiar1234` (deben cambiarla al ingresar) |
| 3 | `proyectos.xlsx` | Proyectos | Excel | 3 proyectos con responsables `lucia`, `martin` y `sofia` |

Primero se ve la vista previa y recién después se confirma. Si un rol o usuario ya existe en la base, la vista previa lo marca como error de fila (por ejemplo, `Analista`); borrá esa fila del archivo o cambiale el nombre.
