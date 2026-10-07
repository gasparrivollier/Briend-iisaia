import csv
import io
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, Response, UploadFile

from ..bulk.base import EntitySpec
from ..bulk.entities import SPECS
from ..bulk.parsing import parse_file
from ..bulk.service import run
from ..errors import APIError, forbidden, not_found
from ..mail import send_email
from ..schemas import CargaResultado
from ..sessions import DB, User, guard

router = APIRouter(
    prefix='/api/carga-masiva', tags=['carga-masiva'], dependencies=[Depends(guard(json_body=False))]
)


def entity_spec(entidad: str, user: User) -> EntitySpec:
    """Resolved before the file is read, so permission errors win over file errors."""
    spec = SPECS.get(entidad)
    if spec is None:
        raise not_found()
    if spec.admin_only and not user.es_admin:
        raise forbidden('Esta carga requiere permisos de administrador.')
    return spec


Spec = Annotated[EntitySpec, Depends(entity_spec)]


@router.get('/{entidad}/plantilla.csv')
def template(spec: Spec):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(spec.example.keys())
    writer.writerow(spec.example.values())
    return Response(
        content=buffer.getvalue().encode('utf-8-sig'),  # BOM so Excel shows accents correctly
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="plantilla-{spec.key}.csv"'},
    )


@router.post('/{entidad}', response_model=CargaResultado)
def upload(
    spec: Spec,
    db: DB,
    user: User,
    request: Request,
    background_tasks: BackgroundTasks,
    archivo: Annotated[UploadFile | None, File()] = None,
    confirmar: bool = False,
):
    settings = request.app.state.settings
    if archivo is None or not archivo.filename:
        raise APIError('Adjuntá un archivo en el campo «archivo».')
    content = archivo.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise APIError(
            f'El archivo supera el tamaño máximo de {settings.max_upload_bytes // (1024 * 1024)} MiB.',
            413,
            'http_413',
        )
    parsed = parse_file(archivo.filename, content, spec.max_rows)
    result, notifications = run(db, user, spec, parsed, confirmar)
    for note in notifications:
        background_tasks.add_task(
            send_email, settings, note.recipients, note.subject, note.body, note.context
        )
    return result
