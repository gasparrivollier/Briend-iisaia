"""Turn an uploaded .csv/.txt/.xlsx into rows keyed by normalised header. No database access."""

import csv
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from openpyxl import load_workbook

from ..errors import APIError
from .cells import blank_to_none, normalize_header

DELIMITERS = ',;\t|'
MAX_LINES = 50_000  # lines scanned, so a sheet full of empty rows cannot keep us busy


@dataclass
class ParsedFile:
    headers: list[str]
    rows: list[tuple[int, dict[str, Any]]]  # (line number in the file, {header: raw cell})


def invalid(message: str, code: str = 'archivo_invalido') -> APIError:
    return APIError(message, 400, code)


def text_rows(content: bytes) -> Iterator[tuple[int, list[Any]]]:
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('cp1252', errors='replace')
    first = next((line for line in text.splitlines() if line.strip()), '')
    delimiter = max(DELIMITERS, key=first.count) if any(d in first for d in DELIMITERS) else ','
    reader = csv.reader(io.StringIO(text, newline=''), delimiter=delimiter)
    try:
        for cells in reader:
            yield reader.line_num, cells
    except csv.Error:
        raise invalid('El archivo de texto no se pudo leer: revisá comillas y delimitadores.') from None


def xlsx_rows(content: bytes) -> Iterator[tuple[int, list[Any]]]:
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise invalid('El archivo .xlsx no es válido.')
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.worksheets[0]
    except Exception:  # openpyxl raises many types for broken workbooks
        raise invalid('El archivo .xlsx no es válido.') from None
    try:
        for number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            yield number, list(row)
    finally:
        workbook.close()


def parse_file(filename: str, content: bytes, max_rows: int) -> ParsedFile:
    name = filename.lower()
    if name.endswith('.xlsx'):
        lines = xlsx_rows(content)
    elif name.endswith(('.csv', '.txt')):
        lines = text_rows(content)
    else:
        raise APIError(
            'Formato no soportado. Subí un archivo .csv, .xlsx o .txt.', 400, 'formato_no_soportado'
        )

    headers: list[str] | None = None
    rows: list[tuple[int, dict[str, Any]]] = []
    for line, cells in lines:
        if line > MAX_LINES:
            raise invalid(f'El archivo supera las {MAX_LINES} líneas.', 'archivo_demasiado_grande')
        if all(blank_to_none(cell) is None for cell in cells):
            continue
        if headers is None:
            headers = ['' if cell is None else normalize_header(cell) for cell in cells]
            duplicated = sorted({h for h in headers if h and headers.count(h) > 1})
            if duplicated:
                raise invalid('Hay columnas repetidas: ' + ', '.join(duplicated) + '.')
            continue
        if len(rows) >= max_rows:
            raise invalid(
                f'El archivo supera el máximo de {max_rows} filas para esta carga.',
                'archivo_demasiado_grande',
            )
        rows.append(
            (line, {headers[i]: cells[i] for i in range(min(len(headers), len(cells))) if headers[i]})
        )
    if headers is None:
        raise invalid('El archivo está vacío.')
    if not rows:
        raise invalid('El archivo no tiene filas de datos debajo de los encabezados.')
    return ParsedFile([h for h in headers if h], rows)
