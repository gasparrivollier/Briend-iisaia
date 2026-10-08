"""Validate a parsed file against an entity spec and, on confirm, insert it in one transaction."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import APIError
from ..models import Proyecto, Recurso
from ..schemas import CargaIssue, CargaResultado
from .base import Context, EntitySpec, Notification, RowProblem
from .parsing import ParsedFile

MAX_ISSUES = 500


def check_headers(spec: EntitySpec, headers: list[str]) -> None:
    canonical = [spec.aliases.get(header, header) for header in headers]
    repeated = sorted({c for c in canonical if c in spec.columns and canonical.count(c) > 1})
    if repeated:
        raise APIError('Hay columnas repetidas: ' + ', '.join(repeated) + '.', 400, 'archivo_invalido')
    missing = [' o '.join(group) for group in spec.required if not set(canonical).intersection(group)]
    if missing:
        raise APIError('Faltan columnas obligatorias: ' + ', '.join(missing) + '.', 400, 'columnas_faltantes')


def run(
    db: Session, user: Recurso, spec: EntitySpec, parsed: ParsedFile, confirm: bool
) -> tuple[CargaResultado, list[Notification]]:
    check_headers(spec, parsed.headers)
    if confirm and spec.locks_projects:
        # Same lock order as the single-record endpoints, so concurrent edits cannot slip past the checks.
        db.scalars(select(Proyecto.proyecto_id).order_by(Proyecto.proyecto_id).with_for_update()).all()
    ctx = Context(db, user)
    warnings = [
        CargaIssue(fila=1, campo=header, mensaje=f'Columna ignorada: «{header}».')
        for header in parsed.headers
        if spec.aliases.get(header, header) not in spec.columns
    ]
    errors: list[CargaIssue] = []
    builders = []
    for line, raw in parsed.rows:
        row = {spec.aliases.get(key, key): value for key, value in raw.items()}
        row = {key: value for key, value in row.items() if key in spec.columns}
        try:
            builders.append(spec.prepare(row, ctx))
        except RowProblem as found:
            errors.extend(CargaIssue(fila=line, campo=c, mensaje=m) for c, m in found.problems)
        warnings.extend(CargaIssue(fila=line, campo=c, mensaje=m) for c, m in ctx.take_warnings())

    created, notifications = 0, []
    if confirm and not errors:
        created, notifications = spec.insert(db, ctx, builders)
        db.commit()
    else:
        db.rollback()  # preview, or confirm blocked by errors: release locks, keep nothing
    result = CargaResultado(
        entidad=spec.key,
        total=len(parsed.rows),
        validas=len(builders),
        errores_total=len(errors),
        errores=errors[:MAX_ISSUES],
        advertencias=warnings[:MAX_ISSUES],
        creadas=created,
        confirmada=created > 0,
    )
    return result, notifications
