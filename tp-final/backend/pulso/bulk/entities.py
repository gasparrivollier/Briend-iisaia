"""Per-entity column maps and row preparers. Each preparer validates one row and returns a
builder; builders only run on confirm (argon2 hashing, for instance, never happens in a preview)."""

from typing import Any

from ..models import Proyecto, Recurso, Rol, Tarea
from ..routers.tasks import OUTSIDE_PROJECT
from ..schemas import ProyectoIn, RecursoIn, RolIn, TareaIn
from ..security import hash_password
from .base import Build, Context, EntitySpec, RowProblem, gather, problem, reference_from, validated
from .cells import blank_to_none, to_date, to_flag, to_number, to_text


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


def prepare_proyectos(raw: dict[str, Any], ctx: Context) -> Build:
    owner, data = gather(
        lambda: reference_from(
            raw, 'owner_id', 'owner', ctx.resource_names, ctx.resource_ids, 'el responsable'
        ),
        lambda: validated(
            ProyectoIn,
            {
                'proyecto_nombre': to_text(raw.get('proyecto_nombre')),
                'fecha_inicio': to_date(raw.get('fecha_inicio')),
                'fecha_fin': to_date(raw.get('fecha_fin')),
                'horas_requeridas': to_number(raw.get('horas_requeridas')),
                'proyect_status': to_text(raw.get('proyect_status')),
                'porcentaje_avance': to_number(raw.get('porcentaje_avance')) or 0,
            },
        ),
    )
    return lambda: Proyecto(
        proyecto_nombre=data.proyecto_nombre,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        horas_requeridas=data.horas_requeridas,
        owner_id=owner,
        proyect_status=data.proyect_status,
        porcentaje_avance=data.porcentaje_avance,
    )


PROYECTOS = EntitySpec(
    key='proyectos',
    label='Proyectos',
    example={
        'proyecto_nombre': 'Portal clientes',
        'fecha_inicio': '2026-10-01',
        'fecha_fin': '2026-12-31',
        'horas_requeridas': '400',
        'owner': 'maria',
        'proyect_status': 'En curso',
        'porcentaje_avance': '0',
    },
    columns=frozenset(
        {
            'proyecto_nombre',
            'fecha_inicio',
            'fecha_fin',
            'horas_requeridas',
            'owner',
            'owner_id',
            'proyect_status',
            'porcentaje_avance',
        }
    ),
    required=(
        ('proyecto_nombre',),
        ('fecha_inicio',),
        ('fecha_fin',),
        ('horas_requeridas',),
        ('owner', 'owner_id'),
        ('proyect_status',),
    ),
    aliases={
        'nombre': 'proyecto_nombre',
        'inicio': 'fecha_inicio',
        'fin': 'fecha_fin',
        'horas': 'horas_requeridas',
        'responsable': 'owner',
        'estado': 'proyect_status',
        'status': 'proyect_status',
        'avance': 'porcentaje_avance',
    },
    prepare=prepare_proyectos,
)


def prepare_tareas(raw: dict[str, Any], ctx: Context) -> Build:
    project, assignee, data = gather(
        lambda: ctx.project_from(raw),
        lambda: reference_from(
            raw, 'recurso_id', 'recurso', ctx.resource_names, ctx.resource_ids, 'el recurso', required=False
        ),
        lambda: validated(
            TareaIn,
            {
                'tarea_nombre': to_text(raw.get('tarea_nombre')),
                'fecha_inicio': to_date(raw.get('fecha_inicio')),
                'fecha_fin': to_date(raw.get('fecha_fin')),
                'porcentaje_avance': to_number(raw.get('porcentaje_avance')) or 0,
            },
        ),
    )
    if not ctx.user.es_admin and project.owner_id != ctx.user.recurso_id:
        raise problem(
            'proyecto', 'Solo el responsable o un administrador puede cargar tareas en este proyecto.'
        )
    if data.fecha_inicio < project.fecha_inicio or data.fecha_fin > project.fecha_fin:
        raise problem('fecha_inicio', OUTSIDE_PROJECT.format(project.fecha_inicio, project.fecha_fin))
    return lambda: Tarea(
        proyecto_id=project.proyecto_id,
        tarea_nombre=data.tarea_nombre,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        porcentaje_avance=data.porcentaje_avance,
        recurso_id=assignee,
    )


TAREAS = EntitySpec(
    key='tareas',
    label='Tareas',
    example={
        'proyecto': 'Portal clientes',
        'tarea_nombre': 'Diseño',
        'fecha_inicio': '2026-10-01',
        'fecha_fin': '2026-10-15',
        'porcentaje_avance': '0',
        'recurso': 'maria',
    },
    columns=frozenset(
        {
            'proyecto',
            'proyecto_id',
            'tarea_nombre',
            'fecha_inicio',
            'fecha_fin',
            'porcentaje_avance',
            'recurso',
            'recurso_id',
        }
    ),
    required=(
        ('proyecto', 'proyecto_id'),
        ('tarea_nombre',),
        ('fecha_inicio',),
        ('fecha_fin',),
    ),
    aliases={
        'tarea': 'tarea_nombre',
        'nombre': 'tarea_nombre',
        'inicio': 'fecha_inicio',
        'fin': 'fecha_fin',
        'avance': 'porcentaje_avance',
        'responsable': 'recurso',
    },
    prepare=prepare_tareas,
    admin_only=False,
    locks_projects=True,
)

SPECS: dict[str, EntitySpec] = {spec.key: spec for spec in (ROLES, RECURSOS, PROYECTOS, TAREAS)}
