"""Per-entity column maps and row preparers. Each preparer validates one row and returns a
builder; builders only run on confirm (argon2 hashing, for instance, never happens in a preview)."""

from typing import Any

from ..models import Recurso, Rol
from ..schemas import RecursoIn, RolIn
from ..security import hash_password
from .base import Build, Context, EntitySpec, RowProblem, validated
from .cells import blank_to_none, to_flag, to_text


def prepare_roles(raw: dict[str, Any], ctx: Context) -> Build:
    data = validated(RolIn, {'rol_descripcion': to_text(raw.get('rol_descripcion'))})
    key = data.rol_descripcion.lower()
    if key in ctx.role_names or key in ctx.seen('rol'):
        raise RowProblem([('rol_descripcion', 'Ya existe un rol con esa descripción.')])
    ctx.seen('rol').add(key)
    return lambda: Rol(rol_descripcion=data.rol_descripcion)


def prepare_recursos(raw: dict[str, Any], ctx: Context) -> Build:
    password = raw.get('password')
    data = validated(
        RecursoIn,
        {
            'recurso_nombre': to_text(raw.get('recurso_nombre')),
            'email': blank_to_none(raw.get('email')),
            'es_admin': to_flag(raw.get('es_admin')),
            'password': '' if password is None else str(password),
        },
    )
    problems = []
    if len(data.password) < 8:
        problems.append(('password', 'La contraseña debe tener al menos 8 caracteres.'))
    key = data.recurso_nombre.lower()
    if key in ctx.resource_names or key in ctx.seen('recurso'):
        problems.append(('recurso_nombre', 'Ya existe un recurso con ese nombre.'))
    if problems:
        raise RowProblem(problems)
    ctx.seen('recurso').add(key)
    return lambda: Recurso(
        recurso_nombre=data.recurso_nombre,
        email=data.email,
        es_admin=data.es_admin,
        password=hash_password(data.password),
        debe_cambiar_password=True,
    )


ROLES = EntitySpec(
    key='roles',
    label='Roles',
    example={'rol_descripcion': 'Analista'},
    columns=frozenset({'rol_descripcion'}),
    required=(('rol_descripcion',),),
    aliases={'rol': 'rol_descripcion', 'descripcion': 'rol_descripcion'},
    prepare=prepare_roles,
)

RECURSOS = EntitySpec(
    key='recursos',
    label='Recursos',
    example={
        'recurso_nombre': 'maria',
        'email': 'maria@empresa.com',
        'es_admin': 'no',
        'password': 'Cambiar1234',
    },
    columns=frozenset({'recurso_nombre', 'email', 'es_admin', 'password'}),
    required=(('recurso_nombre',), ('password',)),
    aliases={
        'nombre': 'recurso_nombre',
        'usuario': 'recurso_nombre',
        'contrasena': 'password',
        'clave': 'password',
    },
    prepare=prepare_recursos,
    max_rows=200,
)

SPECS: dict[str, EntitySpec] = {spec.key: spec for spec in (ROLES, RECURSOS)}
