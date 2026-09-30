from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import APIError, forbidden
from ..models import Proyecto, Recurso, Tarea
from ..queries import columns, get_or_404, reference
from ..schemas import TareaIn, TareaOut
from ..sessions import DB, User, protected
from .projects import editable_project

router = APIRouter(prefix='/api', tags=['tareas'], dependencies=protected)

OUTSIDE_PROJECT = 'Las fechas de la tarea deben estar dentro de las del proyecto ({} → {}).'


def task_rows(db: Session, *conditions) -> list[dict]:
    query = (
        select(Tarea, Recurso.recurso_nombre)
        .outerjoin(Recurso, Recurso.recurso_id == Tarea.recurso_id)
        .where(*conditions)
        .order_by(Tarea.fecha_inicio, Tarea.tarea_id)
    )
    return [columns(task) | {'recurso_nombre': name} for task, name in db.execute(query)]


@router.get('/proyectos/{identifier}/tareas', response_model=list[TareaOut])
def index(identifier: int, db: DB):
    get_or_404(db, Proyecto, identifier)
    return task_rows(db, Tarea.proyecto_id == identifier)


@router.get('/tareas/{identifier}', response_model=TareaOut)
def detail(identifier: int, db: DB):
    get_or_404(db, Tarea, identifier)
    return task_rows(db, Tarea.tarea_id == identifier)[0]


def editable_task(identifier: int, db: DB, user: User) -> Tarea:
    """Loaded before the body is validated, so permission errors win over validation errors."""
    task = get_or_404(db, Tarea, identifier)
    project = db.get(Proyecto, task.proyecto_id)
    if not user.es_admin and project.owner_id != user.recurso_id:
        raise forbidden('Solo el responsable o un administrador puede editar las tareas de este proyecto.')
    return task


def apply(task: Tarea, project_id: int, data: TareaIn, db: DB) -> dict:
    # Row lock: a concurrent change of the project's dates cannot leave this task outside them.
    project = db.get(Proyecto, project_id, with_for_update=True, populate_existing=True)
    if data.fecha_inicio < project.fecha_inicio or data.fecha_fin > project.fecha_fin:
        raise APIError(OUTSIDE_PROJECT.format(project.fecha_inicio, project.fecha_fin))
    task.proyecto_id = project_id
    task.recurso_id = None if data.recurso_id is None else reference(db, Recurso, data.recurso_id)
    for key in ('tarea_nombre', 'fecha_inicio', 'fecha_fin', 'porcentaje_avance'):
        setattr(task, key, getattr(data, key))
    db.add(task)
    db.commit()
    return task_rows(db, Tarea.tarea_id == task.tarea_id)[0]


@router.post('/proyectos/{identifier}/tareas', status_code=201, response_model=TareaOut)
def create(project: Annotated[Proyecto, Depends(editable_project)], data: TareaIn, db: DB):
    return apply(Tarea(), project.proyecto_id, data, db)


@router.put('/tareas/{identifier}', response_model=TareaOut)
def update(task: Annotated[Tarea, Depends(editable_task)], data: TareaIn, db: DB):
    return apply(task, task.proyecto_id, data, db)


@router.delete('/tareas/{identifier}', status_code=204)
def remove(task: Annotated[Tarea, Depends(editable_task)], db: DB):
    db.delete(task)
    db.commit()
    return Response(status_code=204)
