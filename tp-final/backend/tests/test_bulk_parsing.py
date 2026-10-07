import io
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
from pulso.bulk.parsing import parse_file
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
