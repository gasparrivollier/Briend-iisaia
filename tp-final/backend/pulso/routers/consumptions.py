from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import func, select

from ..errors import forbidden
from ..mail import exceeded_hours_message, send_consumption_email, send_email
from ..models import Consumo, Proyecto, Recurso, Rol
from ..queries import columns, consumption_row, consumptions_query, get_or_404, reference
from ..schemas import ConsumoIn, ConsumoListado, ConsumoOut
from ..sessions import DB, User, protected

router = APIRouter(prefix='/api/consumos', tags=['consumos'], dependencies=protected)


@router.get('', response_model=list[ConsumoListado])
def index(db: DB):
    return [consumption_row(*row) for row in db.execute(consumptions_query())]


@router.get('/{identifier}', response_model=ConsumoOut)
def detail(identifier: int, db: DB):
    return columns(get_or_404(db, Consumo, identifier))


def own_consumption(identifier: int, db: DB, user: User) -> Consumo:
    """Loaded before the body is validated, so permission errors win over validation errors."""
    item = get_or_404(db, Consumo, identifier)
    if not user.es_admin and item.recurso_id != user.recurso_id:
        raise forbidden('Solo podés modificar tus propios consumos.')
    return item


Own = Annotated[Consumo, Depends(own_consumption)]


def apply(
    item: Consumo, data: ConsumoIn, db: DB, user: User, request: Request, background_tasks: BackgroundTasks
) -> Consumo:
    resource = reference(db, Recurso, data.recurso_id) if user.es_admin else user.recurso_id
    project_id = reference(db, Proyecto, data.proyecto_id)
    # Serialize budget checks for concurrent consumption writes (lock before changing the item).
    ids = sorted({identifier for identifier in (item.proyecto_id, project_id) if identifier})
    projects = db.scalars(
        select(Proyecto).where(Proyecto.proyecto_id.in_(ids)).order_by(Proyecto.proyecto_id).with_for_update()
    ).all()
    project = next(project for project in projects if project.proyecto_id == project_id)
    total_query = select(func.coalesce(func.sum(Consumo.horas_consumidas), 0)).where(
        Consumo.proyecto_id == project_id
    )
    before = db.scalar(total_query)
    item.proyecto_id = project_id
    item.rol_id = reference(db, Rol, data.rol_id)
    item.recurso_id = resource
    for key in ('fecha_inicio', 'fecha_fin', 'horas_consumidas', 'tarea'):
        setattr(item, key, getattr(data, key))
    db.add(item)
    db.flush()
    after = db.scalar(total_query)
    owner = db.get(Recurso, project.owner_id)
    alert = before <= project.horas_requeridas < after
    subject, body = exceeded_hours_message(project.proyecto_nombre, project.horas_requeridas, after)
    recipients = [owner.email] if owner.email else []
    db.commit()
    if alert:
        background_tasks.add_task(
            send_email, request.app.state.settings, recipients, subject, body, f'Proyecto {project_id}: horas'
        )
    return item


@router.post('', status_code=201, response_model=ConsumoOut)
def create(data: ConsumoIn, db: DB, user: User, request: Request, background_tasks: BackgroundTasks):
    item = apply(Consumo(), data, db, user, request, background_tasks)
    project = get_or_404(db, Proyecto, item.proyecto_id)
    resource = get_or_404(db, Recurso, item.recurso_id)
    owner = get_or_404(db, Recurso, project.owner_id)
    role = get_or_404(db, Rol, item.rol_id)
    recipients = list(
        dict.fromkeys(email.strip().lower() for email in (owner.email, resource.email) if email)
    )
    body = (
        f'Se registró el consumo #{item.consumo_id}.\n\n'
        f'Proyecto: {project.proyecto_nombre}\n'
        f'Recurso: {resource.recurso_nombre}\n'
        f'Rol: {role.rol_descripcion}\n'
        f'Fecha de inicio: {item.fecha_inicio:%d/%m/%Y}\n'
        f'Fecha de fin: {item.fecha_fin:%d/%m/%Y}\n'
        f'Horas consumidas: {item.horas_consumidas:g}\n'
        f'Tarea: {item.tarea}\n'
    )
    background_tasks.add_task(
        send_consumption_email, request.app.state.settings, recipients, body, item.consumo_id
    )
    return item


@router.put('/{identifier}', response_model=ConsumoOut)
def update(
    item: Own, data: ConsumoIn, db: DB, user: User, request: Request, background_tasks: BackgroundTasks
):
    return apply(item, data, db, user, request, background_tasks)


@router.delete('/{identifier}', status_code=204)
def remove(item: Own, db: DB):
    db.delete(item)
    db.commit()
    return Response(status_code=204)
