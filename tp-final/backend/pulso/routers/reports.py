from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from .. import reports
from ..alerts import BUENOS_AIRES
from ..errors import APIError, not_found
from ..models import Consumo, Proyecto, Tarea
from ..queries import consumption_row, consumptions_query, project_summary, projects_query
from ..schemas import ProyectoReporte
from ..sessions import DB, protected
from .tasks import task_rows

router = APIRouter(prefix='/api', tags=['reportes'], dependencies=protected)

PERIODS = ('semana', 'mes')


def today() -> date:
    """The report's "today" (Buenos Aires, like the alerts); a dependency so tests can pin it."""
    return datetime.now(BUENOS_AIRES).date()


@router.get('/proyectos/{identifier}/reporte', response_model=ProyectoReporte)
def report(identifier: int, db: DB, hoy: Annotated[date, Depends(today)], periodo: str = 'semana'):
    if periodo not in PERIODS:
        raise APIError('Seleccioná un período válido (semana o mes).')
    row = db.execute(projects_query().where(Proyecto.proyecto_id == identifier)).first()
    if row is None:
        raise not_found()
    project = project_summary(*row)
    consumptions = [
        consumption_row(*item)
        for item in db.execute(consumptions_query().where(Consumo.proyecto_id == identifier))
    ]
    tasks = task_rows(db, Tarea.proyecto_id == identifier)
    return {
        'proyecto': project,
        'fecha_corte': hoy,
        'periodo': periodo,
        'salud': reports.health(project, hoy),
        'periodos': reports.periods(consumptions, periodo),
        'ritmo': reports.pace(project, consumptions, hoy),
        'ejecucion': reports.execution(project, consumptions, hoy),
        'tareas': reports.task_health(tasks, hoy),
        'distribucion': reports.distribution(consumptions),
    }
