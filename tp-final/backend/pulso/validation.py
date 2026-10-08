"""Spanish messages for Pydantic errors, shared by the error handler and the bulk loader."""

from .schemas import BAD_NUMBER, BAD_REFERENCE, REQUIRED

# Message for a field missing from the body, by the kind of field (mirrors the Flask helpers).
MISSING = {
    'horas_requeridas': BAD_NUMBER,
    'horas_consumidas': BAD_NUMBER,
    'porcentaje_avance': BAD_NUMBER,
    'proyecto_id': BAD_REFERENCE,
    'rol_id': BAD_REFERENCE,
    'fecha_inicio': 'Ingresá fechas válidas.',
    'fecha_fin': 'Ingresá fechas válidas.',
}


def validation_message(error: dict) -> str:
    if error.get('type') == 'pulso':
        return error['msg']
    if error.get('type') == 'missing':
        return MISSING.get(str(error['loc'][-1]), REQUIRED)
    if error.get('type') == 'json_invalid':
        return 'El cuerpo JSON no es válido.'
    return 'Datos inválidos.'
