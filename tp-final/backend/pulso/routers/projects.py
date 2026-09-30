from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from ..errors import APIError, forbidden
from ..models import STATUSES, Consumo, Proyecto, Recurso, Rol, Tarea
from ..queries import (
    consumption_row,
    consumptions_query,
    get_or_404,
    project_summary,
    projects_query,
    reference,
)
from ..schemas import Catalogos, ProyectoDetalle, ProyectoIn, ProyectoOut, ProyectoResumen
from ..sessions import DB, User, protected, require_admin

router = APIRouter(prefix='/api', tags=['proyectos'], dependencies=protected)


@router.get('/catalogos', response_model=Catalogos)
def catalogs(db: DB):
    return {
        'estados': list(STATUSES),
        'recursos': db.scalars(select(Recurso).order_by(func.lower(Recurso.recurso_nombre))).all(),
        'roles': db.scalars(select(Rol).order_by(func.lower(Rol.rol_descripcion))).all(),
    }


@router.get('/proyectos', response_model=list[ProyectoResumen])
def index(db: DB, estado: str = '', responsable: str = ''):
    query = projects_query().order_by(Proyecto.proyecto_id.desc())
    if estado:
        query = query.where(Proyecto.proyect_status == estado)
    if responsable:
        if not responsable.isdigit():
            raise APIError('Seleccioná una referencia válida.')
        query = query.where(Proyecto.owner_id == int(responsable))
    return [project_summary(*row) for row in db.execute(query)]


@router.get('/proyectos/{identifier}', response_model=ProyectoDetalle)
def detail(identifier: int, db: DB):
    row = db.execute(projects_query().where(Proyecto.proyecto_id == identifier)).first()
    if row is None:
        get_or_404(db, Proyecto, identifier)
    query = consumptions_query().where(Consumo.proyecto_id == identifier)
    rows = [consumption_row(*item) for item in db.execute(query)]
    by_resource: dict[str, float] = {}
    by_role: dict[str, float] = {}
    for item in rows:
        name, role = item['recurso_nombre'], item['rol_descripcion']
        by_resource[name] = by_resource.get(name, 0) + item['horas_consumidas']
        by_role[role] = by_role.get(role, 0) + item['horas_consumidas']
    return {
        'proyecto': project_summary(*row),
        'consumos': rows,
        'por_recurso': by_resource,
        'por_rol': by_role,
    }


def editable_project(identifier: int, db: DB, user: User) -> Proyecto:
    """Loaded before the body is validated, so permission errors win over validation errors."""
    project = get_or_404(db, Proyecto, identifier)
    if not user.es_admin and project.owner_id != user.recurso_id:
        raise forbidden('Solo el responsable o un administrador puede editar este proyecto.')
    return project


def apply(project: Proyecto, data: ProyectoIn, db: DB, user: User) -> Proyecto:
    if project.proyecto_id is not None:
        # Same row lock as saving a task, so a task cannot slip outside the new range concurrently.
        db.get(Proyecto, project.proyecto_id, with_for_update=True, populate_existing=True)
        outside = db.scalar(
            select(func.count())
            .select_from(Tarea)
            .where(
                Tarea.proyecto_id == project.proyecto_id,
                (Tarea.fecha_inicio < data.fecha_inicio) | (Tarea.fecha_fin > data.fecha_fin),
            )
        )
        if outside:
            raise APIError(
                f'Hay {outside} tarea(s) fuera de las nuevas fechas del proyecto. '
                'Ajustalas antes de cambiar el rango.'
            )
    if user.es_admin:
        project.owner_id = reference(db, Recurso, data.owner_id)
    for key, value in data.model_dump(exclude={'owner_id'}).items():
        setattr(project, key, value)
    db.add(project)  # only after validation, so autoflush never sees a half-filled row
    db.commit()
    return project


@router.post('/proyectos', status_code=201, response_model=ProyectoOut, dependencies=[Depends(require_admin)])
def create(data: ProyectoIn, db: DB, user: User):
    return apply(Proyecto(), data, db, user)


@router.put('/proyectos/{identifier}', response_model=ProyectoOut)
def update(project: Annotated[Proyecto, Depends(editable_project)], data: ProyectoIn, db: DB, user: User):
    return apply(project, data, db, user)


@router.delete('/proyectos/{identifier}', status_code=204, dependencies=[Depends(require_admin)])
def remove(identifier: int, db: DB):
    db.delete(get_or_404(db, Proyecto, identifier))
    db.commit()
    return Response(status_code=204)
