import io
import time
import zipfile
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
from pulso.bulk.parsing import MAX_COLUMNS, MAX_UNCOMPRESSED, parse_file
from pulso.errors import APIError

from .conftest import xlsx_bytes


def test_normalize_header():
    assert normalize_header(' Contraseña ') == 'contrasena'
    assert normalize_header('Fecha de Inicio') == 'fecha_de_inicio'
    assert normalize_header('Horas-Consumidas') == 'horas_consumidas'


@pytest.mark.parametrize(
    'value,expected',
    [
        ('1,5', '1.5'),
        ('1.200,5', '1200.5'),
        ('1,200.5', '1200.5'),
        (' 12 ', '12'),
        (3, 3),
        (None, None),
        ('', None),
    ],
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
    assert parsed.rows[0] == (
        2,
        {'proyecto': 'Alfa', 'inicio': datetime(2026, 10, 1), 'horas': 1.5, 'id': 3.0},
    )
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


def test_xlsx_with_truncated_sheet_xml_is_rejected():
    original = zipfile.ZipFile(io.BytesIO(xlsx_bytes([['rol'], ['QA'], ['Dev']])))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as broken:
        for item in original.namelist():
            data = original.read(item)
            if item == 'xl/worksheets/sheet1.xml':
                data = data[: len(data) // 2]
            broken.writestr(item, data)
    with pytest.raises(APIError) as caught:
        parse_file('a.xlsx', buffer.getvalue(), 10)
    assert caught.value.status == 400 and caught.value.code == 'archivo_invalido'


def test_xlsx_row_cap_error_is_not_converted_to_invalid_file():
    with pytest.raises(APIError) as caught:
        parse_file('a.xlsx', xlsx_bytes([['rol'], ['A'], ['B'], ['C']]), 2)
    assert caught.value.code == 'archivo_demasiado_grande'


def test_xlsx_styled_empty_rows_far_below_the_data_are_ignored():
    rows = [['rol'], ['QA']] + [[None]] * 59_997 + [[' ']]
    parsed = parse_file('a.xlsx', xlsx_bytes(rows), 10)
    assert parsed.rows == [(2, {'rol': 'QA'})]


def test_csv_unterminated_quote_is_rejected():
    with pytest.raises(APIError) as caught:
        parse_file('a.csv', b'a,b\n"x,1\ny,2\n', 10)
    assert caught.value.status == 400 and caught.value.code == 'archivo_invalido'


def sparse_xlsx(gaps, gap, dimension='A1:XFD1048576'):
    """A tiny workbook declaring the whole sheet as its dimension, with a data row every `gap` lines."""
    workbook = io.BytesIO()
    from openpyxl import Workbook

    Workbook().save(workbook)
    first = '<row r="1"><c r="A1" t="inlineStr"><is><t>rol_descripcion</t></is></c></row>'
    rows = [first] + [
        f'<row r="{1 + k * gap}"><c r="A{1 + k * gap}" t="inlineStr"><is><t>r{k}</t></is></c></row>'
        for k in range(1, gaps + 1)
    ]
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/><sheetData>' + ''.join(rows) + '</sheetData></worksheet>'
    ).encode()
    source = zipfile.ZipFile(workbook)
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in source.infolist():
            data = sheet if item.filename == 'xl/worksheets/sheet1.xml' else source.read(item.filename)
            archive.writestr(item, data)
    return out.getvalue()


def test_xlsx_with_a_huge_declared_dimension_and_sparse_rows_parses_fast():
    started = time.monotonic()
    parsed = parse_file('a.xlsx', sparse_xlsx(3, 1000), 10)
    assert [row['rol_descripcion'] for _, row in parsed.rows] == ['r1', 'r2', 'r3']
    assert time.monotonic() - started < 2


def test_csv_header_with_tens_of_thousands_of_columns_is_rejected_fast():
    content = ','.join(f'c{i}' for i in range(40_000)).encode() + b'\n1\n'
    started = time.monotonic()
    with pytest.raises(APIError) as caught:
        parse_file('a.csv', content, 10)
    assert caught.value.code == 'archivo_invalido' and 'columnas' in str(caught.value)
    assert time.monotonic() - started < 2


def test_header_row_at_the_column_cap_is_accepted_and_one_more_is_not():
    ok = ','.join(f'c{i}' for i in range(MAX_COLUMNS)) + '\n' + ','.join('1' for _ in range(MAX_COLUMNS))
    assert len(parse_file('a.csv', ok.encode(), 10).headers) == MAX_COLUMNS
    wide = [f'c{i}' for i in range(MAX_COLUMNS + 1)]
    for name, content in (
        ('a.csv', (','.join(wide) + '\n1\n').encode()),
        ('a.xlsx', xlsx_bytes([wide, [1]])),
    ):
        with pytest.raises(APIError) as caught:
            parse_file(name, content, 10)
        assert caught.value.code == 'archivo_invalido'


def test_xlsx_with_a_huge_decompressed_size_is_rejected():
    original = zipfile.ZipFile(io.BytesIO(xlsx_bytes([['rol'], ['QA']])))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as bomb:
        for item in original.namelist():
            bomb.writestr(item, original.read(item))
        bomb.writestr('xl/relleno.bin', b'\0' * (MAX_UNCOMPRESSED + 1))
    assert len(buffer.getvalue()) < 1_000_000
    with pytest.raises(APIError) as caught:
        parse_file('a.xlsx', buffer.getvalue(), 10)
    assert caught.value.code == 'archivo_invalido' and 'descomprimido' in str(caught.value)


def test_nul_characters_are_rejected_in_csv():
    # xlsx cannot carry NUL (XML 1.0 forbids it), so only text files need the check
    with pytest.raises(APIError) as caught:
        parse_file('a.csv', b'rol\nQA\x00x\n', 10)
    assert caught.value.code == 'archivo_invalido' and 'nulos' in str(caught.value)
