# Carga masiva (batch upload) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users bulk-load Roles, Recursos, Proyectos, Tareas and Consumos from `.csv`, `.xlsx` or `.txt` files, with a per-row preview before anything is saved.

**Architecture:** A stateless multipart endpoint `POST /api/carga-masiva/{entidad}?confirmar=false|true`. A pure parser turns the file into rows; one `EntitySpec` per entity maps columns, resolves names to ids and validates each row with the existing Pydantic `*In` models. Preview never writes; confirm re-validates the same file and inserts everything in one transaction (all-or-nothing). A Vue view drives preview then confirm.

**Tech Stack:** FastAPI + SQLAlchemy sync + Pydantic (existing), `python-multipart`, `openpyxl`, Vue 3 + TS + openapi-fetch (existing), pytest, Vitest, Playwright.

**Spec:** `/home/gaspi/.claude/plans/are-superpowers-enabled-eventual-bengio.md`, copied to `tp-final/docs/superpowers/specs/2026-10-07-carga-masiva-design.md`.

## Global Constraints

- All user-visible text and API messages in Spanish; code identifiers follow the existing Spanish table/column names and English helper names.
- Backend endpoints are sync `def` (sync SQLAlchemy). Quote style single, line length 110 (`uv run ruff check . && uv run ruff format --check .` must pass).
- Error contract stays `{"error": {"code", "message"}}`. The only new exception to "mutations are JSON + CSRF" is multipart on `/api/carga-masiva/*` (still auth + CSRF).
- Limits: 5 MiB per file (`max_upload_bytes`), 5000 data rows (200 for Recursos, argon2 costs ~50 ms per row).
- Formats: `.csv`, `.xlsx` (first sheet only), `.txt` (delimited text, same parser as csv). Delimiters `, ; \t |`. Encodings `utf-8-sig`, fallback `cp1252`.
- References by name with id fallback, matching `lower()` + trim. Project names are not unique: an ambiguous name is a row error asking for `proyecto_id`.
- Permissions: Roles/Recursos/Proyectos admin only (403 before parsing). Tareas: admin, or owner of that row's project (row error otherwise). Consumos: any user; non-admins always log as themselves.
- `STATUSES` match is exact and case-sensitive after trim.
- Do **not** run `git commit`/`git push` unless the user asks. Where a step says "checkpoint", just run the tests.
- `tp-final/prompts.md` must be updated (Spanish) as work progresses (CLAUDE.md rule).
- Tests need the dev Postgres: `cd tp-final && podman compose up -d db mailpit`.

## Deviation from the approved spec

The spec said confirm with remaining errors returns a `422`-style `carga_invalida`. The frontend `call()` discards the response body on non-2xx, and the UI needs the per-row errors, so confirm-with-errors returns **200** with `confirmada: false`, `creadas: 0` and the same `errores` list. Everything else follows the spec.

## Review Focus

Failure modes the spec implies but that are easy to miss (each has a test in the task that owns the code):

1. Excel-flavoured CSV: `;` delimiter, UTF-8 BOM or cp1252 accents, decimal comma (`1.200,5`), `DD/MM/YYYY` dates, so a file saved by Spanish Excel loads without edits. (Task 2, 5)
2. `.xlsx` cell types: real date cells (datetime), integer ids stored as floats, numbers in text columns, trailing empty rows. (Task 2)
3. Header-only, blank, or whitespace-only files give a clear error, never a successful "0 rows" confirm. (Task 2)
4. Uploading the same Consumos file twice warns about duplicates; confirming the same Roles file twice does not 500 (second confirm reports "ya existe"). (Task 3, 7)
5. Cross-user rules: a non-owner uploading Tareas, and a non-admin naming another person in a Consumos `recurso` column, get row errors, not silent success. (Task 6, 7)

## File structure

| File | Responsibility |
|---|---|
| `backend/pulso/validation.py` (new) | `MISSING` + `validation_message()`, moved out of `main.py` so the loader can reuse them |
| `backend/pulso/bulk/cells.py` (new) | Pure cell converters (header normalisation, dates, numbers, ids, flags, text) |
| `backend/pulso/bulk/parsing.py` (new) | `parse_file(filename, content, max_rows) -> ParsedFile`; csv/txt/xlsx |
| `backend/pulso/bulk/base.py` (new) | `EntitySpec`, `Context` (preloaded lookups), `RowProblem`, `gather`, `reference_from`, `validated` |
| `backend/pulso/bulk/entities.py` (new) | The five `prepare_*` functions, specs and `SPECS` registry; consumption insert + notifications |
| `backend/pulso/bulk/service.py` (new) | `run()` = header check, per-row validation, confirm/insert |
| `backend/pulso/routers/bulk.py` (new) | Endpoints: upload (preview/confirm) and CSV template |
| `backend/pulso/schemas.py` | `CargaIssue`, `CargaResultado` |
| `backend/pulso/sessions.py` | `guard(json_body=False)` variant |
| `backend/pulso/main.py` | Router registration, per-path size limit, import `validation_message` |
| `backend/pulso/mail.py`, `routers/consumptions.py` | `exceeded_hours_message()` shared by single and bulk consumption |
| `deploy/Caddyfile` | 6 MB body limit for `/api/carga-masiva/*` |
| `frontend/src/bulk.ts`, `components/BulkResult.vue`, `views/BulkUploadView.vue` (new) | Entity availability, result table, the screen |
| `frontend/src/api/client.ts`, `router.ts`, `components/AppHeader.vue` | Multipart call, route, nav link |

---

### Task 1: Dependencies, settings and shared validation messages

**Files:**
- Modify: `backend/pyproject.toml`, `backend/uv.lock` (via `uv add`)
- Modify: `backend/pulso/config.py`
- Create: `backend/pulso/validation.py`
- Modify: `backend/pulso/main.py:1-37`
- Test: `backend/tests/test_validation.py`

**Interfaces:**
- Produces: `pulso.validation.validation_message(error: dict) -> str`, `pulso.validation.MISSING: dict[str, str]`, `Settings.max_upload_bytes: int` (5 MiB).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_validation.py`:

```python
import pytest
from pydantic import ValidationError

from pulso.schemas import REQUIRED, RolIn
from pulso.validation import validation_message


def first_error(data):
    with pytest.raises(ValidationError) as caught:
        RolIn.model_validate(data)
    return caught.value.errors()[0]


def test_missing_field_uses_generic_required_message():
    assert validation_message(first_error({})) == REQUIRED


def test_custom_pulso_error_is_forwarded_verbatim():
    assert validation_message(first_error({'rol_descripcion': '   '})) == REQUIRED
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd tp-final/backend && uv run pytest tests/test_validation.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'pulso.validation'`.

- [ ] **Step 3: Install dependencies and add the setting**

Run: `cd tp-final/backend && uv add python-multipart openpyxl`
Expected: `pyproject.toml` gains both entries and `uv.lock` updates.

In `backend/pulso/config.py` add under `max_body_bytes`:

```python
    max_upload_bytes: int = 5 * 1024 * 1024
```

- [ ] **Step 4: Create `backend/pulso/validation.py`** (moved verbatim from `main.py`)

```python
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
```

In `backend/pulso/main.py` delete the `MISSING` dict and `validation_message` function (lines 17-36), and replace the schemas import:

```python
from .schemas import BAD_NUMBER, BAD_REFERENCE, REQUIRED
```
with
```python
from .validation import validation_message
```

- [ ] **Step 5: Run the whole backend suite**

Run: `cd tp-final/backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all pass (132 existing + 2 new), ruff clean.

---

### Task 2: File parsing (cells + csv/txt/xlsx)

**Files:**
- Create: `backend/pulso/bulk/__init__.py` (empty), `backend/pulso/bulk/cells.py`, `backend/pulso/bulk/parsing.py`
- Modify: `backend/tests/conftest.py` (add `xlsx_bytes`)
- Test: `backend/tests/test_bulk_parsing.py`

**Interfaces:**
- Produces (`cells.py`): `normalize_header(text) -> str`, `blank_to_none(v)`, `to_text(v)`, `to_date(v)`, `to_number(v)`, `to_id(v)`, `to_flag(v)`.
- Produces (`parsing.py`): `ParsedFile(headers: list[str], rows: list[tuple[int, dict[str, Any]]])` where each row is `(line_number, {normalized_header: raw_cell})`; `parse_file(filename: str, content: bytes, max_rows: int) -> ParsedFile`; raises `APIError` (400) with codes `formato_no_soportado`, `archivo_invalido`, `archivo_demasiado_grande`.
- Produces (`conftest.py`): `xlsx_bytes(rows: list[list]) -> bytes`.

- [ ] **Step 1: Add the xlsx helper to `backend/tests/conftest.py`**

Add imports `import io` and `from openpyxl import Workbook` at the top, and at the bottom:

```python
def xlsx_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_bulk_parsing.py`:

```python
from datetime import date, datetime

import pytest

from pulso.bulk.cells import (
    normalize_header,
    to_date,
    to_flag,
    to_id,
    to_number,
    to_text,
)
from pulso.bulk.parsing import parse_file
from pulso.errors import APIError

from .conftest import xlsx_bytes


def test_normalize_header():
    assert normalize_header(' Contraseña ') == 'contrasena'
    assert normalize_header('Fecha de Inicio') == 'fecha_de_inicio'
    assert normalize_header('Horas-Consumidas') == 'horas_consumidas'


@pytest.mark.parametrize(
    'value,expected',
    [('1,5', '1.5'), ('1.200,5', '1200.5'), ('1,200.5', '1200.5'), (' 12 ', '12'), (3, 3), (None, None), ('', None)],
)
def test_to_number(value, expected):
    assert to_number(value) == expected


def test_to_date_accepts_iso_dmy_and_datetime():
    assert to_date('2026-10-01') == '2026-10-01'
    assert to_date('01/10/2026') == date(2026, 10, 1)
    assert to_date(datetime(2026, 10, 1, 0, 0)) == date(2026, 10, 1)
    assert to_date('31/02/2026') == '31/02/2026'  # left as-is so iso_date reports "fechas válidas"
    assert to_date('  ') is None


def test_to_id_to_text_to_flag():
    assert to_id(3.0) == 3 and to_id('4.0') == 4 and to_id('5') == '5' and to_id('') is None
    assert to_text(2024) == '2024' and to_text(2.5) == '2.5' and to_text('  x ') == 'x'
    assert to_flag('Sí') is True and to_flag('no') is False and to_flag(None) is False
    assert to_flag('quizás') == 'quizás'


def test_csv_comma_and_blank_lines_keep_real_line_numbers():
    parsed = parse_file('a.csv', b'Rol\nQA\n\n  \nDev\n', 100)
    assert parsed.headers == ['rol']
    assert parsed.rows == [(2, {'rol': 'QA'}), (5, {'rol': 'Dev'})]


def test_csv_semicolon_with_bom_and_accents():
    content = '﻿nombre;contraseña\nJosé;Clave1234\n'.encode()
    parsed = parse_file('a.csv', content, 100)
    assert parsed.headers == ['nombre', 'contrasena']
    assert parsed.rows == [(2, {'nombre': 'José', 'contrasena': 'Clave1234'})]


def test_csv_cp1252_fallback():
    parsed = parse_file('a.csv', 'nombre\nPeña\n'.encode('cp1252'), 100)
    assert parsed.rows[0][1]['nombre'] == 'Peña'


def test_txt_tab_and_pipe_delimiters():
    assert parse_file('a.txt', b'a\tb\n1\t2\n', 10).rows == [(2, {'a': '1', 'b': '2'})]
    assert parse_file('a.txt', b'a|b\n1|2\n', 10).rows == [(2, {'a': '1', 'b': '2'})]


def test_quoted_delimiter_inside_a_cell():
    parsed = parse_file('a.csv', b'a,b\n"x, y",2\n', 10)
    assert parsed.rows[0][1] == {'a': 'x, y', 'b': '2'}


def test_xlsx_reads_first_sheet_with_native_types_and_skips_empty_rows():
    content = xlsx_bytes(
        [
            ['Proyecto', 'Inicio', 'Horas', 'Id'],
            ['Alfa', datetime(2026, 10, 1), 1.5, 3.0],
            [None, None, None, None],
            ['Beta', datetime(2026, 11, 2), 2, 4],
        ]
    )
    parsed = parse_file('a.xlsx', content, 10)
    assert parsed.headers == ['proyecto', 'inicio', 'horas', 'id']
    assert parsed.rows[0] == (2, {'proyecto': 'Alfa', 'inicio': datetime(2026, 10, 1), 'horas': 1.5, 'id': 3.0})
    assert parsed.rows[1][0] == 4


@pytest.mark.parametrize(
    'name,content,code',
    [
        ('a.pdf', b'x', 'formato_no_soportado'),
        ('a', b'x', 'formato_no_soportado'),
        ('a.xlsx', b'not a zip', 'archivo_invalido'),
        ('a.csv', b'', 'archivo_invalido'),
        ('a.csv', b'   \n\n', 'archivo_invalido'),
        ('a.csv', b'rol\n', 'archivo_invalido'),
        ('a.csv', b'rol,rol\nA,B\n', 'archivo_invalido'),
        ('a.csv', b'rol\nA\nB\nC\n', 'archivo_demasiado_grande'),
    ],
)
def test_rejected_files(name, content, code):
    with pytest.raises(APIError) as caught:
        parse_file(name, content, 2)
    assert caught.value.status == 400 and caught.value.code == code


def test_header_only_xlsx_is_rejected():
    with pytest.raises(APIError) as caught:
        parse_file('a.xlsx', xlsx_bytes([['rol']]), 10)
    assert caught.value.code == 'archivo_invalido'
```

- [ ] **Step 3: Run to confirm failure**

Run: `cd tp-final/backend && uv run pytest tests/test_bulk_parsing.py -q`
Expected: FAIL (`ModuleNotFoundError: pulso.bulk`).

- [ ] **Step 4: Implement `backend/pulso/bulk/cells.py`** (and create empty `__init__.py`)

```python
"""Cell conversions from spreadsheet/text values to what the Pydantic schemas accept.

Unconvertible values are returned untouched so the schema validators report the usual Spanish
message instead of this module inventing a new one.
"""

import re
import unicodedata
from datetime import date, datetime
from typing import Any

TRUE_WORDS = {'si', 'sí', 'true', 'verdadero', 'yes', 'y', '1'}
FALSE_WORDS = {'no', 'false', 'falso', 'n', '0'}


def normalize_header(text: Any) -> str:
    plain = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '_', plain.lower()).strip('_')


def blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def to_text(value: Any) -> Any:
    value = blank_to_none(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return str(int(value)) if float(value).is_integer() else str(value)
    return value


def to_date(value: Any) -> Any:
    value = blank_to_none(value)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        match = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', value)
        if match:
            day, month, year = map(int, match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                return value
    return value


def to_number(value: Any) -> Any:
    value = blank_to_none(value)
    if not isinstance(value, str):
        return value
    text = value.replace(' ', '')
    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):  # 1.200,5
            text = text.replace('.', '').replace(',', '.')
        else:  # 1,200.5
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    return text


def to_id(value: Any) -> Any:
    value = blank_to_none(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r'\d+\.0+', value):
        return int(float(value))
    return value


def to_flag(value: Any) -> Any:
    value = blank_to_none(value)
    if value is None:
        return False
    if isinstance(value, str):
        word = value.lower()
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
    return value
```

- [ ] **Step 5: Implement `backend/pulso/bulk/parsing.py`**

```python
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
        raise APIError('Formato no soportado. Subí un archivo .csv, .xlsx o .txt.', 400, 'formato_no_soportado')

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
                f'El archivo supera el máximo de {max_rows} filas para esta carga.', 'archivo_demasiado_grande'
            )
        rows.append((line, {headers[i]: cells[i] for i in range(min(len(headers), len(cells))) if headers[i]}))
    if headers is None:
        raise invalid('El archivo está vacío.')
    if not rows:
        raise invalid('El archivo no tiene filas de datos debajo de los encabezados.')
    return ParsedFile([h for h in headers if h], rows)
```

- [ ] **Step 6: Run the tests**

Run: `cd tp-final/backend && uv run pytest tests/test_bulk_parsing.py -q && uv run ruff check . && uv run ruff format .`
Expected: PASS. If a `to_number` parametrize id fails, fix the converter, not the test (the cases are the spec).

---

### Task 3: Framework, endpoint and Roles end to end

**Files:**
- Create: `backend/pulso/bulk/base.py`, `backend/pulso/bulk/entities.py`, `backend/pulso/bulk/service.py`, `backend/pulso/routers/bulk.py`
- Modify: `backend/pulso/schemas.py` (append result models), `backend/pulso/sessions.py:45-67`, `backend/pulso/main.py`, `backend/tests/conftest.py` (add `upload`)
- Test: `backend/tests/test_bulk_api.py`

**Interfaces:**
- Consumes: `parse_file`, `ParsedFile`, `cells.*` from Task 2; `validation_message` from Task 1.
- Produces (`base.py`):
  - `RowProblem(problems: list[tuple[str | None, str]])`, `problem(campo, mensaje) -> RowProblem`
  - `validated(model, data) -> model instance` (raises `RowProblem` with every error)
  - `gather(*parts: Callable[[], Any]) -> list[Any]` (runs all parts, raises one combined `RowProblem`)
  - `reference_from(raw, id_column, name_column, names, ids, label, required=True) -> int | None`
  - `Context(db, user)` with `.resource_names`, `.resource_ids`, `.role_names`, `.role_ids`, `.projects` (`dict[int, Proyecto]`), `.project_names`, `.seen(key) -> set`, `.warn(campo, mensaje)`, `.take_warnings() -> list[tuple]`, `.project_from(raw) -> Proyecto`
  - `Notification(recipients, subject, body, context)` (NamedTuple)
  - `EntitySpec(key, label, example, columns, required, aliases, prepare, max_rows=5000, admin_only=True, locks_projects=False, insert=default_insert)`; `prepare(row: dict, ctx: Context) -> Callable[[], Base]`; `insert(db, ctx, builders) -> tuple[int, list[Notification]]`
- Produces (`service.py`): `run(db, user, spec, parsed, confirm) -> tuple[CargaResultado, list[Notification]]`.
- Produces (`entities.py`): `SPECS: dict[str, EntitySpec]`.
- Produces (`schemas.py`): `CargaIssue(fila: int, campo: str | None, mensaje: str)`, `CargaResultado(entidad, total, validas, errores_total, errores, advertencias, creadas, confirmada)`.
- Produces (`conftest.py`): `upload(client, entidad, filename, content, confirmar=False) -> Response`.

- [ ] **Step 1: Add the `upload` helper to `backend/tests/conftest.py`**

```python
def upload(client, entidad, filename, content, confirmar=False):
    token = client.get('/api/session').json()['csrf_token']
    if isinstance(content, str):
        content = content.encode()
    return client.post(
        f'/api/carga-masiva/{entidad}',
        params={'confirmar': 'true' if confirmar else 'false'},
        files={'archivo': (filename, content, 'application/octet-stream')},
        headers={'X-CSRF-Token': token},
    )
```

- [ ] **Step 2: Write the failing tests** (Roles only; later tasks append)

Create `backend/tests/test_bulk_api.py`:

```python
import pytest

from .conftest import login, scalar, upload, xlsx_bytes


def roles_csv(*names):
    return 'rol_descripcion\n' + ''.join(f'{name}\n' for name in names)


def summary(response):
    body = response.json()
    return (body['total'], body['validas'], body['errores_total'], body['creadas'], body['confirmada'])


def test_roles_preview_writes_nothing(client, seeded):
    login(client)
    response = upload(client, 'roles', 'roles.csv', roles_csv('QA', 'Dev'))
    assert response.status_code == 200
    assert summary(response) == (2, 2, 0, 0, False)
    assert scalar(seeded, 'SELECT count(*) FROM rol') == 1


def test_roles_confirm_inserts_all(client, seeded):
    login(client)
    response = upload(client, 'roles', 'roles.csv', roles_csv('QA', 'Dev'), confirmar=True)
    assert summary(response) == (2, 2, 0, 2, True)
    assert scalar(seeded, 'SELECT count(*) FROM rol') == 3


def test_roles_one_bad_row_blocks_the_whole_confirm(client, seeded):
    login(client)
    response = upload(client, 'roles', 'roles.csv', roles_csv('QA', 'analista', 'QA'), confirmar=True)
    assert response.status_code == 200
    body = response.json()
    assert (body['creadas'], body['confirmada'], body['errores_total'], body['validas']) == (0, False, 2, 1)
    assert [(e['fila'], e['campo']) for e in body['errores']] == [(3, 'rol_descripcion'), (4, 'rol_descripcion')]
    assert 'ya existe' in body['errores'][0]['mensaje'].lower()
    assert scalar(seeded, 'SELECT count(*) FROM rol') == 1


def test_confirming_the_same_roles_file_twice_does_not_fail_with_500(client, seeded):
    login(client)
    assert upload(client, 'roles', 'roles.csv', roles_csv('QA'), confirmar=True).json()['creadas'] == 1
    second = upload(client, 'roles', 'roles.csv', roles_csv('QA'), confirmar=True)
    assert second.status_code == 200
    assert (second.json()['creadas'], second.json()['errores_total']) == (0, 1)


def test_roles_from_xlsx_and_header_alias(client, seeded):
    login(client)
    content = xlsx_bytes([['Descripción'], ['QA'], ['Dev']])
    assert summary(upload(client, 'roles', 'roles.xlsx', content, confirmar=True)) == (2, 2, 0, 2, True)


def test_missing_required_column_and_ignored_extra_column(client, seeded):
    login(client)
    response = upload(client, 'roles', 'roles.csv', 'otra\nx\n')
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'columnas_faltantes'
    ok = upload(client, 'roles', 'roles.csv', 'rol_descripcion,nota\nQA,hola\n')
    assert ok.json()['advertencias'][0]['campo'] == 'nota'


def test_permissions_and_guard(client, seeded):
    assert upload(client, 'roles', 'roles.csv', roles_csv('QA')).status_code == 401
    login(client, 'ana', 'Personal123')
    denied = upload(client, 'roles', 'roles.csv', roles_csv('QA'))
    assert (denied.status_code, denied.json()['error']['code']) == (403, 'http_403')
    login(client)
    no_csrf = client.post('/api/carga-masiva/roles', files={'archivo': ('r.csv', b'x')})
    assert (no_csrf.status_code, no_csrf.json()['error']['code']) == (400, 'csrf_invalid')


def test_unknown_entity_bad_format_and_missing_file(client, seeded):
    login(client)
    assert upload(client, 'nada', 'a.csv', 'x').status_code == 404
    bad = upload(client, 'roles', 'roles.pdf', 'x')
    assert (bad.status_code, bad.json()['error']['code']) == (400, 'formato_no_soportado')
    token = client.get('/api/session').json()['csrf_token']
    missing = client.post(
        '/api/carga-masiva/roles', files={'otro': ('x.csv', b'x')}, headers={'X-CSRF-Token': token}
    )
    assert missing.status_code == 400 and 'archivo' in missing.json()['error']['message'].lower()


def test_size_limits_apply_in_middleware_and_in_router(client, seeded):
    login(client)
    client.app.state.settings.max_upload_bytes = 50
    in_router = upload(client, 'roles', 'roles.csv', roles_csv(*['x' * 20] * 10))
    assert (in_router.status_code, in_router.json()['error']['code']) == (413, 'http_413')
    in_middleware = upload(client, 'roles', 'roles.csv', b'x' * 200_000)
    assert (in_middleware.status_code, in_middleware.json()['error']['code']) == (413, 'http_413')


def test_json_routes_keep_their_limits_and_415(client, seeded):
    login(client)
    token = client.get('/api/session').json()['csrf_token']
    form = client.post('/api/roles', data={'rol_descripcion': 'x'}, headers={'X-CSRF-Token': token})
    assert form.status_code == 415


def test_template_download(client, seeded):
    login(client)
    response = client.get('/api/carga-masiva/roles/plantilla.csv')
    assert response.status_code == 200
    assert 'plantilla-roles.csv' in response.headers['content-disposition']
    assert response.content.decode('utf-8-sig').splitlines()[0] == 'rol_descripcion'
    assert client.get('/api/carga-masiva/nada/plantilla.csv').status_code == 404
```

(`pytest` import is used by later tasks' parametrised tests; if ruff flags it unused now, add it in the task that needs it.)

- [ ] **Step 3: Run to confirm failure**

Run: `cd tp-final/backend && uv run pytest tests/test_bulk_api.py -q`
Expected: FAIL (404 on `/api/carga-masiva/...` / import errors).

- [ ] **Step 4: Append result schemas to `backend/pulso/schemas.py`**

```python


class CargaIssue(BaseModel):
    fila: int
    campo: str | None = None
    mensaje: str


class CargaResultado(BaseModel):
    entidad: str
    total: int
    validas: int
    errores_total: int
    errores: list[CargaIssue]
    advertencias: list[CargaIssue]
    creadas: int
    confirmada: bool
```

- [ ] **Step 5: Add the multipart guard variant in `backend/pulso/sessions.py`**

Change the signature and the block after the CSRF check:

```python
def guard(require_user: bool = True, allow_pending: bool = False, json_body: bool = True):
    async def dependency(request: Request, state: State) -> None:
        ...  # unchanged up to and including the CSRF check
        if not json_body:  # multipart uploads: auth and CSRF only
            return
        content_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
        ...  # unchanged
```
Update the module docstring's guard-order line to mention: "`json_body=False` skips the 415 and body checks (multipart uploads)".

- [ ] **Step 6: Per-path size limit and router registration in `backend/pulso/main.py`**

Import: `from .routers import alerts, auth, bulk, consumptions, projects, reports, resources, roles, tasks`. Add `bulk` to the `for module in (...)` tuple. Replace the size check inside `limits_and_headers`:

```python
        length = request.headers.get('content-length', '')
        upload = request.url.path.startswith('/api/carga-masiva/')
        # Multipart framing adds a little to the file itself; the router enforces the exact file size.
        limit = settings.max_upload_bytes + 64 * 1024 if upload else settings.max_body_bytes
        shown = settings.max_upload_bytes if upload else settings.max_body_bytes
        if length.isdigit() and int(length) > limit:
            response = error_response(
                413, 'http_413', f'La solicitud supera el tamaño máximo de {shown // (1024 * 1024)} MiB.'
            )
        else:
            response = await call_next(request)
```
The existing 1 MiB message is unchanged (`1024*1024 // 1024*1024 = 1`).

- [ ] **Step 7: Create `backend/pulso/bulk/base.py`**

```python
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
            [(str(item['loc'][0]) if item['loc'] else None, validation_message(item)) for item in error.errors()]
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
            name.lower(): ident for ident, name in db.execute(select(Recurso.recurso_id, Recurso.recurso_nombre))
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
            raise problem('proyecto', f'Hay {len(matches)} proyectos llamados «{given_name}»; usá proyecto_id.')
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
```

- [ ] **Step 8: Create `backend/pulso/bulk/entities.py`** (Roles only for now)

```python
"""Per-entity column maps and row preparers. Each preparer validates one row and returns a
builder; builders only run on confirm (argon2 hashing, for instance, never happens in a preview)."""

from typing import Any

from ..models import Rol
from ..schemas import RolIn
from .base import Build, Context, EntitySpec, RowProblem, validated
from .cells import to_text


def prepare_roles(raw: dict[str, Any], ctx: Context) -> Build:
    data = validated(RolIn, {'rol_descripcion': to_text(raw.get('rol_descripcion'))})
    key = data.rol_descripcion.lower()
    if key in ctx.role_names or key in ctx.seen('rol'):
        raise RowProblem([('rol_descripcion', 'Ya existe un rol con esa descripción.')])
    ctx.seen('rol').add(key)
    return lambda: Rol(rol_descripcion=data.rol_descripcion)


ROLES = EntitySpec(
    key='roles',
    label='Roles',
    example={'rol_descripcion': 'Analista'},
    columns=frozenset({'rol_descripcion'}),
    required=(('rol_descripcion',),),
    aliases={'rol': 'rol_descripcion', 'descripcion': 'rol_descripcion'},
    prepare=prepare_roles,
)

SPECS: dict[str, EntitySpec] = {spec.key: spec for spec in (ROLES,)}
```

- [ ] **Step 9: Create `backend/pulso/bulk/service.py`**

```python
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
```

- [ ] **Step 10: Create `backend/pulso/routers/bulk.py`**

```python
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
```

Note the 413 test uses a ~220-byte body with limit 50 (router path) and a 200 000-byte body (middleware path, over `50 + 64 KiB`).

- [ ] **Step 11: Run the new tests and the whole suite**

Run: `cd tp-final/backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all pass. If `test_json_routes_keep_their_limits_and_415` fails the guard change leaked into JSON routes; re-check Step 5.

- [ ] **Step 12: Regenerate the OpenAPI types and Caddy limit**

Run: `cd tp-final/frontend && npm run gen:api && git -C .. status --short`
Expected: `src/api/schema.d.ts` (and `openapi.json` if tracked) show the new `/api/carga-masiva/...` paths and `CargaResultado`.

In `deploy/Caddyfile` (the `/api/*` block around line 181) keep the 1MB rule for everything except uploads:

```
@upload path /api/carga-masiva/*
handle @upload {
    request_body {
        max_size 6MB
    }
    reverse_proxy api:5000
}
```
placed **before** the existing `/api/*` handle, reusing whatever proxy directive that block already uses (copy its exact `reverse_proxy` options).

---

### Task 4: Recursos

**Files:**
- Modify: `backend/pulso/bulk/entities.py`
- Test: `backend/tests/test_bulk_api.py` (append)

**Interfaces:**
- Consumes: `validated`, `RowProblem`, `Context.resource_names`, `Context.seen`, `to_text`, `to_flag`, `blank_to_none`.
- Produces: `RECURSOS: EntitySpec` registered in `SPECS`.

- [ ] **Step 1: Append the failing tests to `test_bulk_api.py`**

```python
RECURSOS = (
    'recurso_nombre,email,es_admin,password\n'
    'carla,carla@example.com,si,Secreta123\n'
    'dario,,no,Secreta456\n'
)


def test_recursos_confirm_creates_hashed_users_that_must_change_password(client, seeded):
    login(client)
    assert summary(upload(client, 'recursos', 'r.csv', RECURSOS, confirmar=True)) == (2, 2, 0, 2, True)
    assert scalar(seeded, "SELECT es_admin FROM recurso WHERE recurso_nombre='carla'") is True
    assert scalar(seeded, "SELECT debe_cambiar_password FROM recurso WHERE recurso_nombre='dario'") is True
    assert scalar(seeded, "SELECT password FROM recurso WHERE recurso_nombre='dario'").startswith('$argon2')
    logged = login(client, 'dario', 'Secreta456')
    assert logged.status_code == 200 and logged.json()['user']['debe_cambiar_password'] is True


def test_recursos_row_errors(client, seeded):
    login(client)
    content = (
        'nombre,email,es_admin,contraseña\n'
        'ANA,,no,Secreta123\n'  # exists (case-insensitive)
        'eva,no-es-email,no,Secreta123\n'
        'fede,,quizás,Secreta123\n'
        'gina,,no,corta\n'
        'hugo,,no,Secreta123\n'
        'HUGO,,no,Secreta123\n'  # duplicate inside the file
    )
    body = upload(client, 'recursos', 'r.csv', content).json()
    fields = [(e['fila'], e['campo']) for e in body['errores']]
    assert fields == [
        (2, 'recurso_nombre'),
        (3, 'email'),
        (4, 'es_admin'),
        (5, 'password'),
        (7, 'recurso_nombre'),
    ]
    assert body['validas'] == 1


def test_recursos_are_capped_at_200_rows_and_admin_only(client, seeded):
    login(client)
    rows = ''.join(f'u{i},,no,Secreta123\n' for i in range(201))
    too_big = upload(client, 'recursos', 'r.csv', 'recurso_nombre,email,es_admin,password\n' + rows)
    assert (too_big.status_code, too_big.json()['error']['code']) == (400, 'archivo_demasiado_grande')
    login(client, 'ana', 'Personal123')
    assert upload(client, 'recursos', 'r.csv', RECURSOS).status_code == 403
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd tp-final/backend && uv run pytest tests/test_bulk_api.py -q -k recursos`
Expected: FAIL with 404 (entity not registered).

- [ ] **Step 3: Implement in `entities.py`**

Add imports `from ..models import Recurso, Rol`, `from ..schemas import RecursoIn, RolIn`, `from ..security import hash_password`, `from .cells import blank_to_none, to_flag, to_text`, and `gather` is not needed here. Add:

```python
def prepare_recursos(raw: dict[str, Any], ctx: Context) -> Build:
    password = raw.get('password')
    data = validated(
        RecursoIn,
        {
            'recurso_nombre': to_text(raw.get('recurso_nombre')),
            'email': blank_to_none(raw.get('email')),
            'es_admin': to_flag(raw.get('es_admin')),
            'password': '' if password is None else str(password),
        },
    )
    problems = []
    if len(data.password) < 8:
        problems.append(('password', 'La contraseña debe tener al menos 8 caracteres.'))
    key = data.recurso_nombre.lower()
    if key in ctx.resource_names or key in ctx.seen('recurso'):
        problems.append(('recurso_nombre', 'Ya existe un recurso con ese nombre.'))
    if problems:
        raise RowProblem(problems)
    ctx.seen('recurso').add(key)
    return lambda: Recurso(
        recurso_nombre=data.recurso_nombre,
        email=data.email,
        es_admin=data.es_admin,
        password=hash_password(data.password),
        debe_cambiar_password=True,
    )


RECURSOS = EntitySpec(
    key='recursos',
    label='Recursos',
    example={
        'recurso_nombre': 'maria',
        'email': 'maria@empresa.com',
        'es_admin': 'no',
        'password': 'Cambiar1234',
    },
    columns=frozenset({'recurso_nombre', 'email', 'es_admin', 'password'}),
    required=(('recurso_nombre',), ('password',)),
    aliases={
        'nombre': 'recurso_nombre',
        'usuario': 'recurso_nombre',
        'contrasena': 'password',
        'clave': 'password',
    },
    prepare=prepare_recursos,
    max_rows=200,
)
```
and register: `SPECS = {spec.key: spec for spec in (ROLES, RECURSOS)}`.

- [ ] **Step 4: Run tests**

Run: `cd tp-final/backend && uv run pytest tests/test_bulk_api.py -q && uv run ruff check . && uv run ruff format .`
Expected: PASS. The `es_admin` cell `quizás` must give a `flag` error on column `es_admin` (the schema message "es_admin debe ser un booleano.").

---

### Task 5: Proyectos

**Files:**
- Modify: `backend/pulso/bulk/entities.py`
- Test: `backend/tests/test_bulk_api.py` (append)

**Interfaces:**
- Consumes: `gather`, `reference_from`, `ctx.resource_names/ids`, `to_date`, `to_number`, `to_text`.
- Produces: `PROYECTOS: EntitySpec` registered in `SPECS`.

- [ ] **Step 1: Append failing tests**

```python
PROYECTOS = (
    'proyecto_nombre;fecha_inicio;fecha_fin;horas_requeridas;owner;proyect_status;porcentaje_avance\n'
    'Alfa;01/10/2026;31/10/2026;1.200,5;ana;En curso;10\n'
    'Beta;2026-10-01;2026-10-15;40;BRUNO;Pendiente;\n'
)


def test_proyectos_excel_flavoured_csv_loads_without_edits(client, seeded):
    login(client)
    assert summary(upload(client, 'proyectos', 'p.csv', PROYECTOS, confirmar=True)) == (2, 2, 0, 2, True)
    assert scalar(seeded, "SELECT horas_requeridas FROM proyecto WHERE proyecto_nombre='Alfa'") == 1200.5
    assert scalar(seeded, "SELECT owner_id FROM proyecto WHERE proyecto_nombre='Beta'") == 3
    assert scalar(seeded, "SELECT porcentaje_avance FROM proyecto WHERE proyecto_nombre='Beta'") == 0


def test_proyectos_owner_by_id_and_xlsx_date_cells(client, seeded):
    from datetime import datetime

    login(client)
    content = xlsx_bytes(
        [
            ['proyecto_nombre', 'fecha_inicio', 'fecha_fin', 'horas_requeridas', 'owner_id', 'proyect_status'],
            ['Gamma', datetime(2026, 10, 1), datetime(2026, 12, 1), 10, 2.0, 'Pausado'],
        ]
    )
    assert summary(upload(client, 'proyectos', 'p.xlsx', content, confirmar=True)) == (1, 1, 0, 1, True)
    assert scalar(seeded, "SELECT owner_id FROM proyecto WHERE proyecto_nombre='Gamma'") == 2


def test_proyectos_row_errors_are_all_reported(client, seeded):
    login(client)
    content = (
        'proyecto_nombre,fecha_inicio,fecha_fin,horas_requeridas,owner,proyect_status\n'
        'X,2026-10-10,2026-10-01,-5,nadie,Cancelado\n'
    )
    body = upload(client, 'proyectos', 'p.csv', content).json()
    assert {e['campo'] for e in body['errores']} >= {'owner', 'horas_requeridas', 'proyect_status'}
    assert body['validas'] == 0
```

- [ ] **Step 2: Run to confirm failure** (`-k proyectos`, expect 404).

- [ ] **Step 3: Implement in `entities.py`**

Add imports `Proyecto`, `ProyectoIn`, `reference_from`, `gather`, `to_date`, `to_number`. Add:

```python
def prepare_proyectos(raw: dict[str, Any], ctx: Context) -> Build:
    owner, data = gather(
        lambda: reference_from(
            raw, 'owner_id', 'owner', ctx.resource_names, ctx.resource_ids, 'el responsable'
        ),
        lambda: validated(
            ProyectoIn,
            {
                'proyecto_nombre': to_text(raw.get('proyecto_nombre')),
                'fecha_inicio': to_date(raw.get('fecha_inicio')),
                'fecha_fin': to_date(raw.get('fecha_fin')),
                'horas_requeridas': to_number(raw.get('horas_requeridas')),
                'proyect_status': to_text(raw.get('proyect_status')),
                'porcentaje_avance': to_number(raw.get('porcentaje_avance')) or 0,
            },
        ),
    )
    return lambda: Proyecto(
        proyecto_nombre=data.proyecto_nombre,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        horas_requeridas=data.horas_requeridas,
        owner_id=owner,
        proyect_status=data.proyect_status,
        porcentaje_avance=data.porcentaje_avance,
    )


PROYECTOS = EntitySpec(
    key='proyectos',
    label='Proyectos',
    example={
        'proyecto_nombre': 'Portal clientes',
        'fecha_inicio': '2026-10-01',
        'fecha_fin': '2026-12-31',
        'horas_requeridas': '400',
        'owner': 'maria',
        'proyect_status': 'En curso',
        'porcentaje_avance': '0',
    },
    columns=frozenset(
        {
            'proyecto_nombre',
            'fecha_inicio',
            'fecha_fin',
            'horas_requeridas',
            'owner',
            'owner_id',
            'proyect_status',
            'porcentaje_avance',
        }
    ),
    required=(
        ('proyecto_nombre',),
        ('fecha_inicio',),
        ('fecha_fin',),
        ('horas_requeridas',),
        ('owner', 'owner_id'),
        ('proyect_status',),
    ),
    aliases={
        'nombre': 'proyecto_nombre',
        'inicio': 'fecha_inicio',
        'fin': 'fecha_fin',
        'horas': 'horas_requeridas',
        'responsable': 'owner',
        'estado': 'proyect_status',
        'status': 'proyect_status',
        'avance': 'porcentaje_avance',
    },
    prepare=prepare_proyectos,
)
```
`porcentaje_avance` blank gives `None or 0 = 0`; the literal `0` cell also yields `0`. Register: `(ROLES, RECURSOS, PROYECTOS)`.

- [ ] **Step 4: Run tests**

Run: `cd tp-final/backend && uv run pytest tests/test_bulk_api.py -q && uv run ruff check . && uv run ruff format .`
Expected: PASS.

---

### Task 6: Tareas

**Files:**
- Modify: `backend/pulso/bulk/entities.py`
- Test: `backend/tests/test_bulk_api.py` (append)

**Interfaces:**
- Consumes: `Context.project_from`, `reference_from`, `gather`, `routers.tasks.OUTSIDE_PROJECT`.
- Produces: `TAREAS: EntitySpec` (`admin_only=False`, `locks_projects=True`) registered in `SPECS`.

- [ ] **Step 1: Append failing tests** (seed: project 1 "Proyecto ejemplo", owner ana(2), 2026-09-01..2026-09-30)

```python
TAREAS = (
    'proyecto,tarea_nombre,fecha_inicio,fecha_fin,porcentaje_avance,recurso\n'
    'Proyecto ejemplo,Diseño,2026-09-02,2026-09-10,50,bruno\n'
    'Proyecto ejemplo,Pruebas,2026-09-11,2026-09-20,,\n'
)


def test_tareas_owner_can_load_their_project_tasks(client, seeded):
    login(client, 'ana', 'Personal123')
    assert summary(upload(client, 'tareas', 't.csv', TAREAS, confirmar=True)) == (2, 2, 0, 2, True)
    assert scalar(seeded, "SELECT recurso_id FROM tarea WHERE tarea_nombre='Diseño'") == 3
    assert scalar(seeded, "SELECT recurso_id FROM tarea WHERE tarea_nombre='Pruebas'") is None


def test_tareas_non_owner_gets_row_errors_but_admin_may(client, seeded):
    login(client, 'bruno', 'Personal123')
    body = upload(client, 'tareas', 't.csv', TAREAS).json()
    assert (body['validas'], body['errores_total']) == (0, 2)
    assert 'responsable' in body['errores'][0]['mensaje']
    login(client)
    assert summary(upload(client, 'tareas', 't.csv', TAREAS, confirmar=True)) == (2, 2, 0, 2, True)


def test_tareas_dates_outside_project_unknown_and_ambiguous_project(client, seeded):
    with seeded.state.engine.begin() as connection:
        from sqlalchemy import text

        connection.execute(
            text(
                """INSERT INTO proyecto (proyecto_nombre,fecha_inicio,fecha_fin,horas_requeridas,owner_id,
                proyect_status,porcentaje_avance)
                VALUES ('Proyecto ejemplo','2026-09-01','2026-09-30',10,2,'En curso',0)"""
            )
        )
    login(client)
    content = (
        'proyecto,proyecto_id,tarea_nombre,fecha_inicio,fecha_fin,porcentaje_avance\n'
        'Proyecto ejemplo,,Ambigua,2026-09-02,2026-09-03,0\n'  # two projects with that name
        ',1,Fuera,2026-10-02,2026-10-03,0\n'  # outside 2026-09-01..30
        'Inexistente,,Nada,2026-09-02,2026-09-03,0\n'
        ',1,Bien,2026-09-02,2026-09-03,0\n'  # id fallback
    )
    body = upload(client, 'tareas', 't.csv', content).json()
    messages = {e['fila']: e['mensaje'] for e in body['errores']}
    assert 'Hay 2 proyectos' in messages[2]
    assert 'dentro de las del proyecto' in messages[3]
    assert 'No existe el proyecto' in messages[4]
    assert 5 not in messages and body['validas'] == 1
```

- [ ] **Step 2: Run to confirm failure** (`-k tareas`, expect 404).

- [ ] **Step 3: Implement in `entities.py`**

Add imports `Tarea`, `TareaIn`, `from ..routers.tasks import OUTSIDE_PROJECT`. Add:

```python
def prepare_tareas(raw: dict[str, Any], ctx: Context) -> Build:
    project, assignee, data = gather(
        lambda: ctx.project_from(raw),
        lambda: reference_from(
            raw, 'recurso_id', 'recurso', ctx.resource_names, ctx.resource_ids, 'el recurso', required=False
        ),
        lambda: validated(
            TareaIn,
            {
                'tarea_nombre': to_text(raw.get('tarea_nombre')),
                'fecha_inicio': to_date(raw.get('fecha_inicio')),
                'fecha_fin': to_date(raw.get('fecha_fin')),
                'porcentaje_avance': to_number(raw.get('porcentaje_avance')) or 0,
            },
        ),
    )
    if not ctx.user.es_admin and project.owner_id != ctx.user.recurso_id:
        raise problem('proyecto', 'Solo el responsable o un administrador puede cargar tareas en este proyecto.')
    if data.fecha_inicio < project.fecha_inicio or data.fecha_fin > project.fecha_fin:
        raise problem('fecha_inicio', OUTSIDE_PROJECT.format(project.fecha_inicio, project.fecha_fin))
    return lambda: Tarea(
        proyecto_id=project.proyecto_id,
        tarea_nombre=data.tarea_nombre,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        porcentaje_avance=data.porcentaje_avance,
        recurso_id=assignee,
    )


TAREAS = EntitySpec(
    key='tareas',
    label='Tareas',
    example={
        'proyecto': 'Portal clientes',
        'tarea_nombre': 'Diseño',
        'fecha_inicio': '2026-10-01',
        'fecha_fin': '2026-10-15',
        'porcentaje_avance': '0',
        'recurso': 'maria',
    },
    columns=frozenset(
        {
            'proyecto',
            'proyecto_id',
            'tarea_nombre',
            'fecha_inicio',
            'fecha_fin',
            'porcentaje_avance',
            'recurso',
            'recurso_id',
        }
    ),
    required=(
        ('proyecto', 'proyecto_id'),
        ('tarea_nombre',),
        ('fecha_inicio',),
        ('fecha_fin',),
    ),
    aliases={
        'tarea': 'tarea_nombre',
        'nombre': 'tarea_nombre',
        'inicio': 'fecha_inicio',
        'fin': 'fecha_fin',
        'avance': 'porcentaje_avance',
        'responsable': 'recurso',
    },
    prepare=prepare_tareas,
    admin_only=False,
    locks_projects=True,
)
```
Also import `problem` from `.base`. Register: `(ROLES, RECURSOS, PROYECTOS, TAREAS)`.

- [ ] **Step 4: Run tests**

Run: `cd tp-final/backend && uv run pytest -q && uv run ruff check . && uv run ruff format .`
Expected: PASS. If importing `routers.tasks` from `bulk.entities` raises a circular-import error, move the `OUTSIDE_PROJECT` constant to `pulso/validation.py` and import it from there in both places.

---

### Task 7: Consumos (duplicates, one summary email, one exceeded-hours alert)

**Files:**
- Modify: `backend/pulso/mail.py`, `backend/pulso/routers/consumptions.py:60-72`, `backend/pulso/bulk/entities.py`
- Test: `backend/tests/test_bulk_api.py` (append)

**Interfaces:**
- Produces (`mail.py`): `exceeded_hours_message(name: str, required: float, applied: float) -> tuple[str, str]` returning `(subject, body)`; text identical to what `consumptions.apply` sends today.
- Produces (`entities.py`): `CONSUMOS: EntitySpec` (`admin_only=False`, `locks_projects=True`, custom `insert`).
- Consumes: `Notification`, `Context.project_from`, `ctx.user`.

- [ ] **Step 1: Append failing tests** (seed: project 1 needs 10 h, 3 h already by ana on 2026-09-02, role "Analista"; ana(2), bruno(3))

```python
import smtplib  # noqa: F401  (kept next to the smtp fixture below)
from unittest.mock import MagicMock

from sqlalchemy import text


@pytest.fixture
def smtp(monkeypatch):
    transport = MagicMock()
    transport.return_value.__enter__.return_value.send_message.return_value = {}
    monkeypatch.setattr('pulso.mail.smtplib.SMTP', transport)
    return transport.return_value.__enter__.return_value.send_message


CONSUMOS = (
    'proyecto,recurso,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\n'
    'Proyecto ejemplo,ana,Analista,2026-10-01,2026-10-01,4,Uno\n'
    'Proyecto ejemplo,bruno,analista,2026-10-02,2026-10-02,5,Dos\n'
)


def test_consumos_admin_confirm_sends_one_summary_and_one_exceeded_alert(client, seeded, smtp):
    with seeded.state.engine.begin() as connection:
        connection.execute(text("UPDATE recurso SET email='ana@example.com' WHERE recurso_id=2"))
    login(client)
    assert summary(upload(client, 'consumos', 'c.csv', CONSUMOS, confirmar=True)) == (2, 2, 0, 2, True)
    assert scalar(seeded, 'SELECT count(*) FROM consumo') == 3
    subjects = [call.args[0]['Subject'] for call in smtp.call_args_list]
    assert len(subjects) == 2  # never one email per row
    assert sum(s.startswith('URGENTE horas aplicadas excedidas') for s in subjects) == 1  # 3 + 9 > 10
    assert sum(s.startswith('Pulso: 2 consumos') for s in subjects) == 1


def test_consumos_preview_sends_nothing(client, seeded, smtp):
    login(client)
    assert summary(upload(client, 'consumos', 'c.csv', CONSUMOS)) == (2, 2, 0, 0, False)
    smtp.assert_not_called()
    assert scalar(seeded, 'SELECT count(*) FROM consumo') == 1


def test_consumos_plain_user_always_logs_as_themselves(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    own = 'proyecto,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\nProyecto ejemplo,Analista,2026-10-01,2026-10-01,2,Uno\n'
    assert summary(upload(client, 'consumos', 'c.csv', own, confirmar=True)) == (1, 1, 0, 1, True)
    assert scalar(seeded, "SELECT recurso_id FROM consumo WHERE tarea='Uno'") == 2
    other = 'proyecto,recurso,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\nProyecto ejemplo,bruno,Analista,2026-10-01,2026-10-01,2,Dos\n'
    body = upload(client, 'consumos', 'c.csv', other).json()
    assert body['errores'][0]['campo'] == 'recurso' and body['validas'] == 0


def test_consumos_admin_must_name_the_resource(client, seeded, smtp):
    login(client)
    content = 'proyecto,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\nProyecto ejemplo,Analista,2026-10-01,2026-10-01,2,Uno\n'
    assert upload(client, 'consumos', 'c.csv', content).json()['errores'][0]['campo'] == 'recurso'


def test_consumos_reuploading_the_same_file_warns_about_duplicates(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    row = 'proyecto,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\nProyecto ejemplo,Analista,2026-09-02,2026-09-02,3,diseño\n'
    first = upload(client, 'consumos', 'c.csv', row).json()  # equals the seeded consumption
    assert (first['validas'], first['errores_total'], len(first['advertencias'])) == (1, 0, 1)
    twice = row + 'Proyecto ejemplo,Analista,2026-10-05,2026-10-05,1,Nuevo\nProyecto ejemplo,Analista,2026-10-05,2026-10-05,1,nuevo\n'
    again = upload(client, 'consumos', 'c.csv', twice).json()
    assert len(again['advertencias']) == 2  # seeded duplicate + repeated row inside the file
    assert again['advertencias'][0]['fila'] == 2 and again['validas'] == 3


def test_consumos_twelve_hours_per_day_rule_and_unknown_role(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    content = (
        'proyecto,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\n'
        'Proyecto ejemplo,Analista,2026-10-01,2026-10-01,13,Mucho\n'
        'Proyecto ejemplo,Inexistente,2026-10-01,2026-10-01,2,Rol\n'
    )
    body = upload(client, 'consumos', 'c.csv', content).json()
    assert 'no pueden superar 12' in body['errores'][0]['mensaje']
    assert body['errores'][1]['campo'] == 'rol'
```

- [ ] **Step 2: Run to confirm failure** (`-k consumos`, expect 404).

- [ ] **Step 3: Extract the shared message**

In `backend/pulso/mail.py` append:

```python
def exceeded_hours_message(name: str, required: float, applied: float) -> tuple[str, str]:
    """Subject and body of the 'horas excedidas' alert (single consumption and bulk load)."""
    subject = f'URGENTE horas aplicadas excedidas {name}'
    body = f'Proyecto: {name}\nHoras requeridas: {required:g}\nHoras aplicadas: {applied:g}\n'
    return subject, body
```

In `backend/pulso/routers/consumptions.py` import it (`from ..mail import exceeded_hours_message, send_consumption_email, send_email`) and replace the `subject = ...` / `body = (...)` lines in `apply` with:

```python
    subject, body = exceeded_hours_message(project.proyecto_nombre, project.horas_requeridas, after)
```

Run `uv run pytest tests/test_consumption_mail.py tests/test_consumption_hours_limit.py -q`; expected PASS (behaviour unchanged).

- [ ] **Step 4: Implement in `entities.py`**

Add imports `func`, `select` (`from sqlalchemy import func, select`), `Session`, `Consumo`, `Recurso`, `ConsumoIn`, `exceeded_hours_message`, `Notification`. Add:

```python
RESOLVED = 0  # ids are resolved from names separately; the placeholder lets the schema check the rest


def consumption_resource(raw: dict[str, Any], ctx: Context) -> int:
    resource = reference_from(
        raw,
        'recurso_id',
        'recurso',
        ctx.resource_names,
        ctx.resource_ids,
        'el recurso',
        required=ctx.user.es_admin,
    )
    if ctx.user.es_admin:
        return resource
    if resource not in (None, ctx.user.recurso_id):
        raise problem('recurso', 'Solo podés cargar consumos propios.')
    return ctx.user.recurso_id


def existing_consumptions(db: Session, project_id: int) -> set[tuple]:
    rows = db.execute(
        select(
            Consumo.recurso_id,
            Consumo.fecha_inicio,
            Consumo.fecha_fin,
            Consumo.horas_consumidas,
            Consumo.tarea,
            Consumo.rol_id,
        ).where(Consumo.proyecto_id == project_id)
    )
    return {(r[0], r[1], r[2], r[3], r[4].lower(), r[5]) for r in rows}


def prepare_consumos(raw: dict[str, Any], ctx: Context) -> Build:
    project, role, resource, data = gather(
        lambda: ctx.project_from(raw),
        lambda: reference_from(raw, 'rol_id', 'rol', ctx.role_names, ctx.role_ids, 'el rol'),
        lambda: consumption_resource(raw, ctx),
        lambda: validated(
            ConsumoIn,
            {
                'proyecto_id': RESOLVED,
                'rol_id': RESOLVED,
                'fecha_inicio': to_date(raw.get('fecha_inicio')),
                'fecha_fin': to_date(raw.get('fecha_fin')),
                'horas_consumidas': to_number(raw.get('horas_consumidas')),
                'tarea': to_text(raw.get('tarea')),
            },
        ),
    )
    key = (resource, data.fecha_inicio, data.fecha_fin, data.horas_consumidas, data.tarea.lower(), role)
    cache = ctx.seen('existing-consumptions')
    known = ctx.seen('consumption-keys')
    if project.proyecto_id not in cache:
        cache.add(project.proyecto_id)
        known.update((project.proyecto_id, *existing) for existing in existing_consumptions(ctx.db, project.proyecto_id))
    full_key = (project.proyecto_id, *key)
    if full_key in known:
        ctx.warn('tarea', 'Ya existe un consumo idéntico; se cargará igual.')
    known.add(full_key)
    return lambda: Consumo(
        proyecto_id=project.proyecto_id,
        recurso_id=resource,
        rol_id=role,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        horas_consumidas=data.horas_consumidas,
        tarea=data.tarea,
    )


def project_totals(db: Session, ids: list[int]) -> dict[int, float]:
    rows = db.execute(
        select(Consumo.proyecto_id, func.coalesce(func.sum(Consumo.horas_consumidas), 0))
        .where(Consumo.proyecto_id.in_(ids))
        .group_by(Consumo.proyecto_id)
    )
    return {project_id: total for project_id, total in rows}


def insert_consumptions(db: Session, ctx: Context, builders: list[Build]) -> tuple[int, list[Notification]]:
    """One summary email per project and one 'horas excedidas' alert per project that crosses its budget."""
    items = [build() for build in builders]
    ids = sorted({item.proyecto_id for item in items})
    before = project_totals(db, ids)
    db.add_all(items)
    db.flush()
    after = project_totals(db, ids)
    notes: list[Notification] = []
    for project_id in ids:
        project = ctx.projects[project_id]
        mine = [item for item in items if item.proyecto_id == project_id]
        owner = db.get(Recurso, project.owner_id)
        people = [owner, *(db.get(Recurso, item.recurso_id) for item in mine)]
        recipients = list(dict.fromkeys(p.email.strip().lower() for p in people if p.email))
        added = sum(item.horas_consumidas for item in mine)
        notes.append(
            Notification(
                recipients,
                f'Pulso: {len(mine)} consumos cargados en {project.proyecto_nombre}',
                f'Se cargaron {len(mine)} consumos en el proyecto {project.proyecto_nombre}.\n'
                f'Horas agregadas: {added:g}\nHoras aplicadas en total: {after[project_id]:g}\n'
                f'Horas requeridas: {project.horas_requeridas:g}\n',
                f'Proyecto {project_id}: carga masiva',
            )
        )
        if before.get(project_id, 0) <= project.horas_requeridas < after[project_id]:
            subject, body = exceeded_hours_message(
                project.proyecto_nombre, project.horas_requeridas, after[project_id]
            )
            alert_to = [owner.email] if owner.email else []
            notes.append(Notification(alert_to, subject, body, f'Proyecto {project_id}: horas'))
    return len(items), notes


CONSUMOS = EntitySpec(
    key='consumos',
    label='Consumos',
    example={
        'proyecto': 'Portal clientes',
        'recurso': 'maria',
        'rol': 'Analista',
        'fecha_inicio': '2026-10-05',
        'fecha_fin': '2026-10-05',
        'horas_consumidas': '6',
        'tarea': 'Reunión de relevamiento',
    },
    columns=frozenset(
        {
            'proyecto',
            'proyecto_id',
            'recurso',
            'recurso_id',
            'rol',
            'rol_id',
            'fecha_inicio',
            'fecha_fin',
            'horas_consumidas',
            'tarea',
        }
    ),
    required=(
        ('proyecto', 'proyecto_id'),
        ('rol', 'rol_id'),
        ('fecha_inicio',),
        ('fecha_fin',),
        ('horas_consumidas',),
        ('tarea',),
    ),
    aliases={
        'inicio': 'fecha_inicio',
        'fin': 'fecha_fin',
        'horas': 'horas_consumidas',
        'actividad': 'tarea',
        'usuario': 'recurso',
    },
    prepare=prepare_consumos,
    admin_only=False,
    locks_projects=True,
    insert=insert_consumptions,
)
```
Register: `(ROLES, RECURSOS, PROYECTOS, TAREAS, CONSUMOS)`. (`ctx.seen(...)` doubles as a generic per-upload scratch set; the duplicate-key logic above uses two of them.)

- [ ] **Step 5: Run the full backend suite and lint**

Run: `cd tp-final/backend && uv run pytest -q && uv run ruff check . && uv run ruff format .`
Expected: PASS. If `test_consumos_admin_confirm_sends...` sees 0 emails, the background tasks did not run: confirm `upload` in `routers/bulk.py` adds them via `background_tasks`. In the duplicate test, the third row (`Nuevo`/`nuevo` lowercased) is the in-file repeat, the first row duplicates the seed.

---

### Task 8: Frontend (client, availability rules, result component, view, route)

**Files:**
- Modify: `frontend/src/api/client.ts`, `frontend/src/router.ts`, `frontend/src/components/AppHeader.vue`, `frontend/src/styles/main.css`
- Create: `frontend/src/bulk.ts`, `frontend/src/components/BulkResult.vue`, `frontend/src/views/BulkUploadView.vue`
- Test: `frontend/tests/unit/bulk.spec.ts`, `frontend/tests/unit/client.spec.ts` (append), `frontend/tests/unit/router.spec.ts` (check)

**Interfaces:**
- Consumes: generated `Schemas['CargaResultado']` (Task 3, Step 12), `api.projects`.
- Produces: `api.bulkUpload(entity: string, file: File, confirm: boolean)`, `api.bulkTemplateUrl(entity: string): string`, `availableEntities(user: User, projects: Project[]): BulkEntity[]`, `ACCEPT`.

- [ ] **Step 1: Write the failing unit tests**

Create `frontend/tests/unit/bulk.spec.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { Project, User } from '@/api/client'
import { availableEntities } from '@/bulk'

const user = (over: Partial<User>) =>
  ({ recurso_id: 2, recurso_nombre: 'ana', es_admin: false, debe_cambiar_password: false, ...over }) as User
const project = (owner_id: number) => ({ proyecto_id: 1, owner_id }) as Project

describe('availableEntities', () => {
  it('offers everything to admins in dependency order', () => {
    expect(availableEntities(user({ es_admin: true }), []).map((e) => e.key)).toEqual([
      'roles',
      'recursos',
      'proyectos',
      'tareas',
      'consumos',
    ])
  })
  it('offers consumos to everyone and tareas only to project owners', () => {
    expect(availableEntities(user({}), [project(9)]).map((e) => e.key)).toEqual(['consumos'])
    expect(availableEntities(user({}), [project(2)]).map((e) => e.key)).toEqual(['tareas', 'consumos'])
  })
})
```

Append to `frontend/tests/unit/client.spec.ts` inside the `describe`:

```ts
  it('uploads a file with the CSRF token to the entity endpoint and the confirm flag', async () => {
    const fetch = mockFetch(
      json({ user: null, csrf_token: 'tok' }),
      json({ entidad: 'roles', total: 1, validas: 1, errores_total: 0, errores: [], advertencias: [], creadas: 0, confirmada: false }),
    )
    await api.session()
    const result = await api.bulkUpload('roles', new File(['rol_descripcion\nQA\n'], 'roles.csv'), false)
    const request = fetch.mock.calls[1]![0]
    expect(result.validas).toBe(1)
    expect(request.method).toBe('POST')
    expect(new URL(request.url).pathname).toBe('/api/carga-masiva/roles')
    expect(new URL(request.url).searchParams.get('confirmar')).toBe('false')
    expect(request.headers.get('X-CSRF-Token')).toBe('tok')
  })
```
(The multipart body itself is verified end to end by the Playwright test in Task 9; jsdom's `FormData` is not understood by the Node `Request` that Vitest uses, so the unit test deliberately does not read the body.)

- [ ] **Step 2: Run to confirm failure**

Run: `cd tp-final/frontend && npm test`
Expected: FAIL (`@/bulk` not found, `api.bulkUpload` undefined).

- [ ] **Step 3: Add the API calls to `frontend/src/api/client.ts`** (inside `api`, after `roles` block)

```ts
  bulkUpload: (entity: string, file: File, confirm: boolean) => {
    const form = new FormData()
    form.append('archivo', file)
    return call(
      http.POST('/api/carga-masiva/{entidad}', {
        params: { path: { entidad: entity }, query: { confirmar: confirm } },
        body: {} as never, // the real body is the FormData below; the browser sets the multipart boundary
        bodySerializer: () => form,
      }),
    )
  },
  bulkTemplateUrl: (entity: string) => `/api/carga-masiva/${entity}/plantilla.csv`,
```
If `vue-tsc` rejects the `bodySerializer` return type, cast it: `bodySerializer: () => form as unknown as string`. openapi-fetch 0.17 removes the JSON `Content-Type` automatically for `FormData` bodies; if the request still goes out as `application/json`, add `request.headers.delete('Content-Type')` in the `onRequest` hook when `request.body` is a `FormData`.

- [ ] **Step 4: Create `frontend/src/bulk.ts`**

```ts
import type { Project, User } from '@/api/client'

export type BulkKey = 'roles' | 'recursos' | 'proyectos' | 'tareas' | 'consumos'
export type BulkEntity = { key: BulkKey; label: string; columns: string }

export const ACCEPT = '.csv,.txt,.xlsx'

// Dependency order: a file cannot reference rows created by the same upload.
const ENTITIES: BulkEntity[] = [
  { key: 'roles', label: 'Roles', columns: 'rol_descripcion' },
  { key: 'recursos', label: 'Recursos', columns: 'recurso_nombre, email, es_admin, password (mín. 8 caracteres)' },
  {
    key: 'proyectos',
    label: 'Proyectos',
    columns:
      'proyecto_nombre, fecha_inicio, fecha_fin, horas_requeridas, owner (nombre del recurso), proyect_status, porcentaje_avance',
  },
  {
    key: 'tareas',
    label: 'Tareas',
    columns: 'proyecto (o proyecto_id), tarea_nombre, fecha_inicio, fecha_fin, porcentaje_avance, recurso',
  },
  {
    key: 'consumos',
    label: 'Consumos',
    columns: 'proyecto (o proyecto_id), recurso, rol, fecha_inicio, fecha_fin, horas_consumidas, tarea',
  },
]

/** What the user may load: admins everything, owners their tasks, everyone their own consumptions. */
export function availableEntities(user: User, projects: Project[]): BulkEntity[] {
  if (user.es_admin) return ENTITIES
  const ownsProject = projects.some((p) => p.owner_id === user.recurso_id)
  return ENTITIES.filter((e) => e.key === 'consumos' || (e.key === 'tareas' && ownsProject))
}
```

- [ ] **Step 5: Create `frontend/src/components/BulkResult.vue`**

```vue
<script setup lang="ts">
import type { Schemas } from '@/api/client'

defineProps<{ result: Schemas['CargaResultado']; busy: boolean }>()
defineEmits<{ confirm: [] }>()
</script>

<template>
  <section class="panel" aria-live="polite">
    <h2>Vista previa</h2>
    <p>
      <strong>{{ result.total }}</strong> filas leídas · <strong>{{ result.validas }}</strong> válidas ·
      <strong>{{ result.errores_total }}</strong> errores
    </p>

    <div v-if="result.errores_total" class="table-responsive">
      <p class="status status-pausado">Corregí el archivo y volvé a subirlo: no se guardó nada.</p>
      <table class="table">
        <caption>Errores por fila</caption>
        <thead><tr><th>Fila</th><th>Campo</th><th>Error</th></tr></thead>
        <tbody>
          <tr v-for="(issue, index) in result.errores" :key="index">
            <td>{{ issue.fila }}</td><td>{{ issue.campo ?? '—' }}</td><td>{{ issue.mensaje }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="result.errores_total > result.errores.length" class="muted">
        Se muestran los primeros {{ result.errores.length }} errores.
      </p>
    </div>

    <div v-if="result.advertencias.length" class="table-responsive">
      <table class="table">
        <caption>Advertencias (no impiden la carga)</caption>
        <thead><tr><th>Fila</th><th>Campo</th><th>Aviso</th></tr></thead>
        <tbody>
          <tr v-for="(issue, index) in result.advertencias" :key="index">
            <td>{{ issue.fila }}</td><td>{{ issue.campo ?? '—' }}</td><td>{{ issue.mensaje }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="actions">
      <button v-if="!result.errores_total && result.validas" class="btn btn-primary" :disabled="busy" @click="$emit('confirm')">
        Confirmar carga de {{ result.validas }} filas
      </button>
    </div>
  </section>
</template>
```

- [ ] **Step 6: Create `frontend/src/views/BulkUploadView.vue`**

```vue
<script setup lang="ts">
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Schemas } from '@/api/client'
import { ACCEPT, availableEntities } from '@/bulk'
import BulkResult from '@/components/BulkResult.vue'
import LoadState from '@/components/LoadState.vue'
import PageHeading from '@/components/PageHeading.vue'
import SelectField from '@/components/SelectField.vue'
import { handleError, notice, showNotice } from '@/composables/notice'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const router = useRouter()
const queryClient = useQueryClient()
const projects = useQuery({ queryKey: ['projects', 'bulk'], queryFn: () => api.projects({}), refetchOnWindowFocus: false })

const entities = computed(() => (session.user ? availableEntities(session.user, projects.data.value ?? []) : []))
const options = computed(() => entities.value.map((e) => ({ value: e.key, label: e.label })))
const entity = ref('')
const selected = computed(() => entities.value.find((e) => e.key === entity.value))
const file = ref<File | null>(null)
const result = ref<Schemas['CargaResultado'] | null>(null)
const busy = ref(false)
const input = ref<HTMLInputElement | null>(null)

watch(entity, () => (result.value = null))

function pick(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null
  result.value = null
}

async function send(confirm: boolean) {
  if (!entity.value || !file.value) return
  busy.value = true
  notice.text = ''
  try {
    const response = await api.bulkUpload(entity.value, file.value, confirm)
    if (response.confirmada) {
      await queryClient.invalidateQueries()
      showNotice(`Se cargaron ${response.creadas} registros de ${selected.value?.label.toLowerCase()}.`, 'success')
      result.value = null
      file.value = null
      if (input.value) input.value.value = ''
    } else {
      result.value = response
    }
  } catch (error) {
    await handleError(error, router)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <PageHeading title="Carga masiva" subtitle="Subí un archivo .csv, .xlsx o .txt; vas a ver una vista previa antes de guardar." />
  <LoadState :loading="projects.isPending.value" :error="projects.error.value" @retry="projects.refetch()">
    <form class="panel editor" @submit.prevent="send(false)">
      <SelectField v-model="entity" name="entidad" label="¿Qué querés cargar?" :options="options" />
      <p v-if="selected" class="muted">
        Columnas: {{ selected.columns }}.
        <a :href="api.bulkTemplateUrl(selected.key)" download>Descargar plantilla</a>
      </p>
      <div class="field">
        <label for="archivo">Archivo (.csv, .xlsx o .txt, hasta 5 MiB)</label>
        <input id="archivo" ref="input" type="file" class="form-control" :accept="ACCEPT" required @change="pick" />
      </div>
      <div class="actions">
        <button class="btn btn-primary" :disabled="busy || !entity || !file">Vista previa</button>
      </div>
    </form>
    <BulkResult v-if="result" :result="result" :busy="busy" @confirm="send(true)" />
  </LoadState>
</template>
```
Match what `ProjectsView.vue` does for the global `notice` banner (the layout already renders it); do not add a second banner here.

- [ ] **Step 7: Route and nav link**

In `frontend/src/router.ts`, before the catch-all route:

```ts
  { path: '/carga-masiva', name: 'bulk-upload', component: () => import('@/views/BulkUploadView.vue'), meta: { title: 'Carga masiva' } },
```
In `frontend/src/components/AppHeader.vue`, after the Proyectos link: `<RouterLink to="/carga-masiva">Carga masiva</RouterLink>`.
Add minimal `.table caption` styling only if the existing CSS lacks it (check `main.css` first; reuse existing table classes).

- [ ] **Step 8: Run unit tests, typecheck and build**

Run: `cd tp-final/frontend && npm test && npx vue-tsc --noEmit && npm run build`
Expected: PASS. `tests/unit/router.spec.ts` may enumerate routes; update its expectation if it lists them.

---

### Task 9: End-to-end test, docs and log

**Files:**
- Modify: `frontend/e2e/flows.spec.ts` (append), `docs/API.md`, `docs/ESPECIFICACION.md`, `docs/PLAN.md`, `docs/VALIDACION.md`, `README.md`, `../CLAUDE.md`, `prompts.md`
- Create: `docs/superpowers/specs/2026-10-07-carga-masiva-design.md` (copy of the approved spec)

**Interfaces:**
- Consumes: the finished feature; admin credentials `admin` / `AdminNueva1` and role `Analista` created earlier in the e2e story.

- [ ] **Step 1: Append the e2e test to `frontend/e2e/flows.spec.ts`**

```ts
test('admin bulk-loads roles: errors block the confirm, a fixed file loads', async ({ page }) => {
  await login(page, 'admin', 'AdminNueva1')
  await page.getByRole('link', { name: 'Carga masiva' }).click()
  await page.getByLabel('¿Qué querés cargar?').selectOption('roles')
  const upload = (name: string, text: string) =>
    page.setInputFiles('#archivo', { name, mimeType: 'text/csv', buffer: Buffer.from(text) })

  await upload('roles.csv', 'rol_descripcion\nAnalista\nQA\n') // "Analista" already exists
  await page.getByRole('button', { name: 'Vista previa' }).click()
  await expect(page.getByText('Ya existe un rol con esa descripción.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Confirmar carga/ })).toHaveCount(0)

  await upload('roles.csv', 'rol_descripcion\nQA\nSoporte\n')
  await page.getByRole('button', { name: 'Vista previa' }).click()
  await page.getByRole('button', { name: 'Confirmar carga de 2 filas' }).click()
  await expect(page.getByText('Se cargaron 2 registros de roles.')).toBeVisible()

  await page.getByRole('link', { name: 'Roles' }).click()
  await expect(page.getByRole('cell', { name: 'Soporte' })).toBeVisible()
})
```

- [ ] **Step 2: Run the e2e suite**

Run: `cd tp-final/frontend && npm run test:e2e`
Expected: all flows pass, including the new one (it uploads a real multipart body, which is the proof for the client wiring). If it fails on the `Content-Type`, apply the `onRequest` fix described in Task 8 Step 3.

- [ ] **Step 3: Copy the spec and update the docs (Spanish)**

- `cp /home/gaspi/.claude/plans/are-superpowers-enabled-eventual-bengio.md docs/superpowers/specs/2026-10-07-carga-masiva-design.md`
- `docs/API.md`: new section "Carga masiva": `POST /api/carga-masiva/{entidad}?confirmar=` (multipart, campo `archivo`, formatos, límites, respuesta `CargaResultado`, códigos `formato_no_soportado`, `archivo_invalido`, `archivo_demasiado_grande`, `columnas_faltantes`, 413) y `GET /api/carga-masiva/{entidad}/plantilla.csv`; aclarar que es la única excepción a "toda mutación es JSON" y que sigue exigiendo sesión y CSRF; incluir el mapa de columnas por entidad y las reglas de resolución por nombre.
- `docs/ESPECIFICACION.md`: reemplazar la línea pendiente de cargas masivas por la descripción implementada y la excepción multipart (línea 25).
- `README.md`: fila de permisos de la carga masiva (Roles/Recursos/Proyectos admin; Tareas admin o responsable; Consumos cualquiera) y quitar "CSV" de lo pendiente (línea ~208).
- `docs/PLAN.md` y `docs/VALIDACION.md`: marcar la fase como hecha y registrar los resultados de las pruebas del Paso 4.
- `../CLAUDE.md`: actualizar el párrafo de arquitectura (CSV import ya no está "not started"; mencionar `backend/pulso/bulk/`, `routers/bulk.py`, `views/BulkUploadView.vue`, y la excepción multipart del guard) y la nota de dependencias (`python-multipart`, `openpyxl`).

- [ ] **Step 4: Final verification**

Run:
```
cd tp-final/backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd ../frontend && npm test && npm run gen:api && git -C .. status --short && npm run build
```
Expected: every suite green; `gen:api` produces no diff against what Task 3 generated (CI fails on drift).

Manual check (record in `VALIDACION.md`): with the dev stack running, upload one `.csv`, one `.xlsx` and one `.txt` in load order (Roles → Recursos → Proyectos → Tareas → Consumos), confirm each, and check the rows and the Mailpit summary email at `http://127.0.0.1:8025`.

- [ ] **Step 5: Update `tp-final/prompts.md`**

Append the actions of the implementation (files created and changed, commands run with their results, failures and fixes), in Spanish, under the existing entry for this feature. No commit unless the user asks.

---

## Self-review

**Spec coverage:** formats and parsing (Task 2); five entities with the mapped columns, aliases and required groups (Tasks 3-7); preview-then-confirm, stateless, all-or-nothing, 200-with-`confirmada=false` deviation (Task 3, noted at the top); name-with-id references and ambiguous project names (Tasks 3, 6); permissions incl. per-row Tareas and self-only Consumos (Tasks 3, 6, 7); emails summary + single alert (Task 7); guard variant, per-path size limits, Caddy (Task 3); deps (Task 1); template endpoint (Task 3); frontend route, availability rules, preview and confirm (Task 8); tests per layer and e2e (Tasks 1-9); docs and the mandatory log (Task 9). Out-of-scope items are not planned.

**Placeholder scan:** no TBD/TODO; the only conditional instructions are explicit fallbacks tied to a named failure (circular import, `bodySerializer` typing, `Content-Type`).

**Type consistency:** `EntitySpec.prepare` returns `Build` everywhere; `insert` signature matches `default_insert` and `insert_consumptions`; `CargaResultado` fields (`errores_total`, `creadas`, `confirmada`) are the ones the tests, the service and the Vue component use; `Notification` is built only in `entities.py` and consumed only in `routers/bulk.py`; template example keys equal the column names the specs accept.
