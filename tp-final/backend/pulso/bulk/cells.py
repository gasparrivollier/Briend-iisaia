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
