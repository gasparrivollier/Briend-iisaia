"""Request/response schemas.

Input validators reproduce the rules of the Flask `common.py` helpers (same Spanish messages):
numbers and IDs may be JSON numbers or numeric strings; booleans, objects, lists, NaN and
infinity are rejected. Every validator raises PydanticCustomError('pulso', ...) so the
error handler can forward the message verbatim.
"""

import math
import re
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, ValidationInfo, model_validator
from pydantic_core import PydanticCustomError

from .models import STATUSES

REQUIRED = 'Completá todos los campos obligatorios.'
BAD_NUMBER = 'Ingresá valores numéricos válidos.'
OUT_OF_RANGE = 'Las horas deben ser positivas y el avance debe estar entre 0 y 100.'
BAD_REFERENCE = 'Seleccioná una referencia válida.'
BAD_DATE = 'Ingresá fechas válidas.'


def fail(message: str):
    return PydanticCustomError('pulso', message)


def _string(value: Any, info: ValidationInfo, strip: bool) -> str:
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise fail(f'{info.field_name}: se esperaba texto.')
    return value.strip() if strip else value


def required_text(value: Any, info: ValidationInfo) -> str:
    value = _string(value, info, strip=True)
    if not value:
        raise fail(REQUIRED)
    return value


def email_address(value: Any) -> str | None:
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        raise fail('Ingresá un email válido, por ejemplo nombre@empresa.com.')
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(
        r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+",
        value,
    ):
        raise fail('Ingresá un email válido, por ejemplo nombre@empresa.com.')
    return value


def raw_text(value: Any, info: ValidationInfo) -> str:
    """Passwords: not stripped, may be empty (endpoints decide)."""
    return _string(value, info, strip=False)


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise fail(BAD_NUMBER)
    try:
        value = float(value)
    except ValueError:
        raise fail(BAD_NUMBER) from None
    if not math.isfinite(value):
        raise fail(OUT_OF_RANGE)
    return value


def positive_hours(value: Any) -> float:
    value = _number(value)
    if value <= 0:
        raise fail(OUT_OF_RANGE)
    return value


def percentage(value: Any) -> float:
    value = _number(value)
    if not 0 <= value <= 100:
        raise fail(OUT_OF_RANGE)
    return value


def identifier(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise fail(BAD_REFERENCE)
    try:
        return int(value)
    except ValueError:
        raise fail(BAD_REFERENCE) from None


def optional_identifier(value: Any) -> int | None:
    return None if value is None or value == '' else identifier(value)


def iso_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise fail(BAD_DATE)
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise fail(BAD_DATE) from None


def flag(value: Any) -> bool:
    if not isinstance(value, bool | int) or value not in (0, 1):
        raise fail('es_admin debe ser un booleano.')
    return bool(value)


def status(value: Any, info: ValidationInfo) -> str:
    value = required_text(value, info)
    if value not in STATUSES:
        raise fail('Seleccioná un estado válido.')
    return value


Text = Annotated[str, BeforeValidator(required_text)]
Password = Annotated[str, BeforeValidator(raw_text)]
Hours = Annotated[float, BeforeValidator(positive_hours)]
Percentage = Annotated[float, BeforeValidator(percentage)]
Id = Annotated[int, BeforeValidator(identifier)]
OptionalId = Annotated[int | None, BeforeValidator(optional_identifier)]
IsoDate = Annotated[date, BeforeValidator(iso_date)]
Flag = Annotated[bool, BeforeValidator(flag)]
Status = Annotated[str, BeforeValidator(status)]


class DateRange(BaseModel):
    fecha_inicio: IsoDate
    fecha_fin: IsoDate

    @model_validator(mode='after')
    def ordered(self):
        if self.fecha_fin < self.fecha_inicio:
            raise fail('La fecha de fin no puede ser anterior al inicio.')
        return self


# ---- Inputs -------------------------------------------------------------------------------


class LoginIn(BaseModel):
    recurso_nombre: Text
    password: Password


class PasswordIn(BaseModel):
    actual: Password
    password: Password
    confirmacion: Password


class ProyectoIn(DateRange):
    proyecto_nombre: Text
    horas_requeridas: Hours
    owner_id: Id | None = None  # required for admins; ignored for project owners
    proyect_status: Status
    porcentaje_avance: Percentage


class ConsumoIn(DateRange):
    proyecto_id: Id
    recurso_id: Id | None = None  # required for admins; plain users always log their own hours
    horas_consumidas: Hours
    tarea: Text
    rol_id: Id

    @model_validator(mode='after')
    def daily_hours_limit(self):
        days = (self.fecha_fin - self.fecha_inicio).days + 1
        maximum = 12 * days
        if self.horas_consumidas > maximum:
            raise fail(
                f'Las horas consumidas no pueden superar {maximum} horas '
                f'(12 horas por día durante {days} días, ambas fechas incluidas).'
            )
        return self


class TareaIn(DateRange):
    tarea_nombre: Text
    porcentaje_avance: Percentage
    recurso_id: OptionalId = None  # optional assignee


class RecursoIn(BaseModel):
    email: Annotated[str | None, BeforeValidator(email_address)] = None
    recurso_nombre: Text
    es_admin: Flag = False
    password: Password = ''  # on update: empty keeps the current password


class RolIn(BaseModel):
    rol_descripcion: Text


# ---- Outputs ------------------------------------------------------------------------------


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UsuarioOut(Out):
    email: str | None = None
    recurso_id: int
    recurso_nombre: str
    es_admin: bool
    debe_cambiar_password: bool


class SesionOut(BaseModel):
    user: UsuarioOut | None
    csrf_token: str


class RolOut(Out):
    rol_id: int
    rol_descripcion: str


class RecursoRef(Out):
    recurso_id: int
    recurso_nombre: str


class Catalogos(BaseModel):
    estados: list[str]
    recursos: list[RecursoRef]
    roles: list[RolOut]


class ProyectoOut(Out):
    proyecto_id: int
    proyecto_nombre: str
    fecha_inicio: date
    fecha_fin: date
    horas_requeridas: float
    owner_id: int
    proyect_status: str
    porcentaje_avance: float


class ProyectoResumen(ProyectoOut):
    responsable: str
    horas_consumidas: float
    saldo: float
    exceso: float
    porcentaje_consumo: float


class ConsumoOut(Out):
    consumo_id: int
    proyecto_id: int
    recurso_id: int
    fecha_inicio: date
    fecha_fin: date
    horas_consumidas: float
    tarea: str
    rol_id: int


class ConsumoListado(ConsumoOut):
    proyecto_nombre: str
    recurso_nombre: str
    rol_descripcion: str


class TareaOut(Out):
    tarea_id: int
    proyecto_id: int
    tarea_nombre: str
    fecha_inicio: date
    fecha_fin: date
    porcentaje_avance: float
    recurso_id: int | None
    recurso_nombre: str | None


class ProyectoDetalle(BaseModel):
    proyecto: ProyectoResumen
    consumos: list[ConsumoListado]
    por_recurso: dict[str, float]
    por_rol: dict[str, float]
