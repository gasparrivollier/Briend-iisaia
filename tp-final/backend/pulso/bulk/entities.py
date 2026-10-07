"""Per-entity column maps and row preparers. Each preparer validates one row and returns a
builder; builders only run on confirm (argon2 hashing, for instance, never happens in a preview)."""

from typing import Any

from ..models import Rol
from ..schemas import RolIn
from .base import Build, Context, EntitySpec, RowProblem, validated
from .cells import to_text


def prepare_roles(raw: dict[str, Any], ctx: Context) -> Build:
    data = validated(RolIn, {'rol_descripcion': to_text(raw.get('rol_descripcion'))})
    key = data.rol_descripcion.lower()
    if key in ctx.role_names or key in ctx.seen('rol'):
        raise RowProblem([('rol_descripcion', 'Ya existe un rol con esa descripción.')])
    ctx.seen('rol').add(key)
    return lambda: Rol(rol_descripcion=data.rol_descripcion)


ROLES = EntitySpec(
    key='roles',
    label='Roles',
    example={'rol_descripcion': 'Analista'},
    columns=frozenset({'rol_descripcion'}),
    required=(('rol_descripcion',),),
    aliases={'rol': 'rol_descripcion', 'descripcion': 'rol_descripcion'},
    prepare=prepare_roles,
)

SPECS: dict[str, EntitySpec] = {spec.key: spec for spec in (ROLES,)}
