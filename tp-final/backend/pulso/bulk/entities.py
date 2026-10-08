"""Per-entity column maps and row preparers. Each preparer validates one row and returns a
builder; builders only run on confirm (argon2 hashing, for instance, never happens in a preview)."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..mail import exceeded_hours_message
from ..models import Consumo, Proyecto, Recurso, Rol, Tarea
from ..routers.tasks import OUTSIDE_PROJECT
from ..schemas import ConsumoIn, ProyectoIn, RecursoIn, RolIn, TareaIn
from ..security import hash_password
from .base import (
    Build,
    Context,
    EntitySpec,
    Notification,
    RowProblem,
    gather,
    problem,
    reference_from,
    validated,
)
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

RESOLVED = 0  # ids are resolved from names separately; the placeholder lets the schema check the rest


def consumption_resource(raw: dict[str, Any], ctx: Context) -> int:
    resource = reference_from(
        raw,
        'recurso_id',
        'recurso',
        ctx.resource_names,
        ctx.resource_ids,
        'el recurso',
        required=ctx.user.es_admin,
    )
    if ctx.user.es_admin:
        return resource
    if resource not in (None, ctx.user.recurso_id):
        raise problem('recurso', 'Solo podés cargar consumos propios.')
    return ctx.user.recurso_id


def existing_consumptions(db: Session, project_id: int) -> set[tuple]:
    rows = db.execute(
        select(
            Consumo.recurso_id,
            Consumo.fecha_inicio,
            Consumo.fecha_fin,
            Consumo.horas_consumidas,
            Consumo.tarea,
            Consumo.rol_id,
        ).where(Consumo.proyecto_id == project_id)
    )
    return {(r[0], r[1], r[2], r[3], r[4].lower(), r[5]) for r in rows}


def prepare_consumos(raw: dict[str, Any], ctx: Context) -> Build:
    project, role, resource, data = gather(
        lambda: ctx.project_from(raw),
        lambda: reference_from(raw, 'rol_id', 'rol', ctx.role_names, ctx.role_ids, 'el rol'),
        lambda: consumption_resource(raw, ctx),
        lambda: validated(
            ConsumoIn,
            {
                'proyecto_id': RESOLVED,
                'rol_id': RESOLVED,
                'fecha_inicio': to_date(raw.get('fecha_inicio')),
                'fecha_fin': to_date(raw.get('fecha_fin')),
                'horas_consumidas': to_number(raw.get('horas_consumidas')),
                'tarea': to_text(raw.get('tarea')),
            },
        ),
    )
    key = (resource, data.fecha_inicio, data.fecha_fin, data.horas_consumidas, data.tarea.lower(), role)
    cache = ctx.seen('existing-consumptions')
    known = ctx.seen('consumption-keys')
    if project.proyecto_id not in cache:
        cache.add(project.proyecto_id)
        known.update(
            (project.proyecto_id, *existing)
            for existing in existing_consumptions(ctx.db, project.proyecto_id)
        )
    full_key = (project.proyecto_id, *key)
    if full_key in known:
        ctx.warn('tarea', 'Ya existe un consumo idéntico; se cargará igual.')
    known.add(full_key)
    return lambda: Consumo(
        proyecto_id=project.proyecto_id,
        recurso_id=resource,
        rol_id=role,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        horas_consumidas=data.horas_consumidas,
        tarea=data.tarea,
    )


def project_totals(db: Session, ids: list[int]) -> dict[int, float]:
    rows = db.execute(
        select(Consumo.proyecto_id, func.coalesce(func.sum(Consumo.horas_consumidas), 0))
        .where(Consumo.proyecto_id.in_(ids))
        .group_by(Consumo.proyecto_id)
    )
    return {project_id: total for project_id, total in rows}


def insert_consumptions(db: Session, ctx: Context, builders: list[Build]) -> tuple[int, list[Notification]]:
    """One summary email per project and one 'horas excedidas' alert per project that crosses its budget."""
    items = [build() for build in builders]
    ids = sorted({item.proyecto_id for item in items})
    before = project_totals(db, ids)
    db.add_all(items)
    db.flush()
    after = project_totals(db, ids)
    notes: list[Notification] = []
    for project_id in ids:
        project = ctx.projects[project_id]
        mine = [item for item in items if item.proyecto_id == project_id]
        owner = db.get(Recurso, project.owner_id)
        people = [owner, *(db.get(Recurso, item.recurso_id) for item in mine)]
        recipients = list(dict.fromkeys(p.email.strip().lower() for p in people if p.email))
        added = sum(item.horas_consumidas for item in mine)
        notes.append(
            Notification(
                recipients,
                f'Pulso: {len(mine)} consumos cargados en {project.proyecto_nombre}',
                f'Se cargaron {len(mine)} consumos en el proyecto {project.proyecto_nombre}.\n'
                f'Horas agregadas: {added:g}\nHoras aplicadas en total: {after[project_id]:g}\n'
                f'Horas requeridas: {project.horas_requeridas:g}\n',
                f'Proyecto {project_id}: carga masiva',
            )
        )
        if before.get(project_id, 0) <= project.horas_requeridas < after[project_id]:
            subject, body = exceeded_hours_message(
                project.proyecto_nombre, project.horas_requeridas, after[project_id]
            )
            alert_to = [owner.email] if owner.email else []
            notes.append(Notification(alert_to, subject, body, f'Proyecto {project_id}: horas'))
    return len(items), notes


CONSUMOS = EntitySpec(
    key='consumos',
    label='Consumos',
    example={
        'proyecto': 'Portal clientes',
        'recurso': 'maria',
        'rol': 'Analista',
        'fecha_inicio': '2026-10-05',
        'fecha_fin': '2026-10-05',
        'horas_consumidas': '6',
        'tarea': 'Reunión de relevamiento',
    },
    columns=frozenset(
        {
            'proyecto',
            'proyecto_id',
            'recurso',
            'recurso_id',
            'rol',
            'rol_id',
            'fecha_inicio',
            'fecha_fin',
            'horas_consumidas',
            'tarea',
        }
    ),
    required=(
        ('proyecto', 'proyecto_id'),
        ('rol', 'rol_id'),
        ('fecha_inicio',),
        ('fecha_fin',),
        ('horas_consumidas',),
        ('tarea',),
    ),
    aliases={
        'inicio': 'fecha_inicio',
        'fin': 'fecha_fin',
        'horas': 'horas_consumidas',
        'actividad': 'tarea',
        'usuario': 'recurso',
    },
    prepare=prepare_consumos,
    admin_only=False,
    locks_projects=True,
    insert=insert_consumptions,
)

SPECS: dict[str, EntitySpec] = {spec.key: spec for spec in (ROLES, RECURSOS, PROYECTOS, TAREAS, CONSUMOS)}
