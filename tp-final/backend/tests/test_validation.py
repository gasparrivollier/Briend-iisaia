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
