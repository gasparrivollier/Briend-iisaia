"""Shared pieces of the bulk loader: row problems, lookup context and the entity spec."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NamedTuple

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticCustomError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Base, Proyecto, Recurso, Rol
from ..schemas import BAD_REFERENCE, identifier
from ..validation import validation_message
from .cells import to_id, to_text

Build = Callable[[], Base]


class RowProblem(Exception):
    """Every problem found in one row, as (column or None, Spanish message)."""

    def __init__(self, problems: list[tuple[str | None, str]]):
        super().__init__(problems)
        self.problems = problems


def problem(column: str | None, message: str) -> RowProblem:
    return RowProblem([(column, message)])


def validated[M: BaseModel](model: type[M], data: dict[str, Any]) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise RowProblem(
            [
                (str(item['loc'][0]) if item['loc'] else None, validation_message(item))
                for item in error.errors()
            ]
        ) from None


def gather(*parts: Callable[[], Any]) -> list[Any]:
    """Run every part so one pass reports all problems of a row; raise them together."""
    results: list[Any] = []
    problems: list[tuple[str | None, str]] = []
    for part in parts:
        try:
            results.append(part())
        except RowProblem as found:
            problems.extend(found.problems)
            results.append(None)
    if problems:
        raise RowProblem(problems)
    return results


def reference_from(
    raw: dict[str, Any],
    id_column: str,
    name_column: str,
    names: dict[str, int],
    ids: set[int],
    label: str,
    required: bool = True,
) -> int | None:
    """Resolve a related record from an id column (wins) or a case-insensitive name column."""
    given_id, given_name = to_id(raw.get(id_column)), to_text(raw.get(name_column))
    if given_id is not None:
        try:
            found = identifier(given_id)
        except PydanticCustomError:
            raise problem(id_column, BAD_REFERENCE) from None
        if found not in ids:
            raise problem(id_column, f'No existe {label} con id {found}.')
        return found
    if given_name is not None:
        found = names.get(str(given_name).lower())
        if found is None:
            raise problem(name_column, f'No existe {label} «{given_name}».')
        return found
    if required:
        raise problem(name_column, f'Indicá {label} ({name_column} o {id_column}).')
    return None


class Notification(NamedTuple):
    recipients: list[str]
    subject: str
    body: str
    context: str


class Context:
    """Lookups loaded once per upload, so validating a row never queries the database."""

    def __init__(self, db: Session, user: Recurso):
        self.db = db
        self.user = user
        self.resource_names = {
            name.lower(): ident
            for ident, name in db.execute(select(Recurso.recurso_id, Recurso.recurso_nombre))
        }
        self.resource_ids = set(self.resource_names.values())
        self.role_names = {
            desc.lower(): ident for ident, desc in db.execute(select(Rol.rol_id, Rol.rol_descripcion))
        }
        self.role_ids = set(self.role_names.values())
        self.projects: dict[int, Proyecto] = {p.proyecto_id: p for p in db.scalars(select(Proyecto))}
        self.project_names: dict[str, list[int]] = {}
        for project in self.projects.values():
            self.project_names.setdefault(project.proyecto_nombre.lower(), []).append(project.proyecto_id)
        self._seen: dict[str, set] = {}
        self._warnings: list[tuple[str | None, str]] = []

    def seen(self, key: str) -> set:
        return self._seen.setdefault(key, set())

    def warn(self, column: str | None, message: str) -> None:
        self._warnings.append((column, message))

    def take_warnings(self) -> list[tuple[str | None, str]]:
        taken, self._warnings = self._warnings, []
        return taken

    def project_from(self, raw: dict[str, Any]) -> Proyecto:
        given_id, given_name = to_id(raw.get('proyecto_id')), to_text(raw.get('proyecto'))
        if given_id is not None:
            try:
                found = identifier(given_id)
            except PydanticCustomError:
                raise problem('proyecto_id', BAD_REFERENCE) from None
            if found not in self.projects:
                raise problem('proyecto_id', f'No existe el proyecto con id {found}.')
            return self.projects[found]
        if given_name is None:
            raise problem('proyecto', 'Indicá el proyecto (proyecto o proyecto_id).')
        matches = self.project_names.get(str(given_name).lower(), [])
        if not matches:
            raise problem('proyecto', f'No existe el proyecto «{given_name}».')
        if len(matches) > 1:
            raise problem(
                'proyecto', f'Hay {len(matches)} proyectos llamados «{given_name}»; usá proyecto_id.'
            )
        return self.projects[matches[0]]


def default_insert(db: Session, ctx: Context, builders: list[Build]) -> tuple[int, list[Notification]]:
    items = [build() for build in builders]
    db.add_all(items)
    db.flush()
    return len(items), []


@dataclass(frozen=True)
class EntitySpec:
    key: str  # URL segment
    label: str
    example: dict[str, str]  # template header + one example row (insertion order = column order)
    columns: frozenset[str]  # every accepted canonical column (example columns plus id fallbacks)
    required: tuple[tuple[str, ...], ...]  # each group: at least one of these columns must be a header
    aliases: dict[str, str]  # normalised header -> canonical column
    prepare: Callable[[dict[str, Any], Context], Build]
    max_rows: int = 5000
    admin_only: bool = True
    locks_projects: bool = False
    insert: Callable[[Session, Context, list[Build]], tuple[int, list[Notification]]] = default_insert
