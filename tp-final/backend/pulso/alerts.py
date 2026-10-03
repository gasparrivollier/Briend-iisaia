"""Daily deadline checks, run by a separate worker, not by each API process."""

import logging
import time
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import Settings
from .db import make_engine
from .mail import send_email
from .models import Proyecto, Recurso, RevisionDiaria

logger = logging.getLogger('pulso.alerts')
# Buenos Aires currently uses UTC-3 throughout the year.
BUENOS_AIRES = timezone(timedelta(hours=-3), 'America/Buenos_Aires')


class AlertResult(BaseModel):
    fecha: date
    vencidos: int = 0
    enviados: int = 0
    fallidos: int = 0
    sin_email: int = 0
    en_ejecucion: bool = False


def run_deadline_check(engine, settings: Settings, today: date, *, manual: bool = False) -> AlertResult:
    result = AlertResult(fecha=today)
    with Session(engine) as db, db.begin():
        # One worker/check at a time, including manual invocations on other processes.
        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(70451003)')):
            result.en_ejecucion = True
            return result
        if not manual and db.get(RevisionDiaria, today):
            return result
        rows = db.execute(
            select(Proyecto, Recurso.email)
            .join(Recurso, Recurso.recurso_id == Proyecto.owner_id)
            .where(Proyecto.fecha_fin < today)
            .order_by(Proyecto.proyecto_id)
        )
        for project, email in rows:
            result.vencidos += 1
            if not email:
                result.sin_email += 1
                continue
            sent = send_email(
                settings,
                [email] if email else [],
                f'URGENTE Fecha de finalizacion excedida {project.proyecto_nombre}',
                f'Proyecto: {project.proyecto_nombre}\n'
                f'Fecha actual: {today:%d/%m/%Y}\n'
                f'Fecha prevista de finalización: {project.fecha_fin:%d/%m/%Y}\n',
                f'Proyecto {project.proyecto_id}: vencimiento',
            )
            result.enviados += int(sent)
            result.fallidos += int(not sent)
        if not manual:
            db.add(RevisionDiaria(fecha=today))
        logger.info('Revisión %s: %s avisos enviados.', today, result.enviados)
        return result


def check_deadlines(engine, settings: Settings, today: date) -> int:
    return run_deadline_check(engine, settings, today).enviados


def run_worker():
    settings = Settings()
    engine = make_engine(settings.database_url)
    logging.basicConfig(level=logging.INFO)
    try:
        while True:
            now = datetime.now(BUENOS_AIRES)
            if now.hour >= 9:
                try:
                    check_deadlines(engine, settings, now.date())
                except Exception:
                    logger.exception('No se pudo completar la revisión diaria.')
            time.sleep(60)
    finally:
        engine.dispose()


if __name__ == '__main__':
    run_worker()
