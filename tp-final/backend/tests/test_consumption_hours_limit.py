import pytest
from pydantic import ValidationError

from pulso.schemas import ConsumoIn
from tests.conftest import consumption_data, login, mutate, post, scalar


@pytest.mark.parametrize(
    'start,end,maximum',
    [
        ('2026-10-03', '2026-10-03', 12),
        ('2026-10-03', '2026-10-05', 36),
        ('2026-09-30', '2026-10-01', 24),
        ('2028-02-28', '2028-03-01', 36),
    ],
)
def test_inclusive_limit(start, end, maximum):
    data = consumption_data() | {'fecha_inicio': start, 'fecha_fin': end}
    for hours in (0.5, maximum - 0.01, maximum):
        assert ConsumoIn(**(data | {'horas_consumidas': hours})).horas_consumidas == hours
    with pytest.raises(ValidationError, match=f'no pueden superar {maximum}'):
        ConsumoIn(**(data | {'horas_consumidas': maximum + 0.01}))


def test_create_and_update_enforce_limit(client, seeded):
    login(client)
    data = consumption_data() | {'fecha_inicio': '2026-10-01', 'fecha_fin': '2026-10-01'}
    response = post(client, '/api/consumos', data | {'horas_consumidas': 12.01})
    assert response.status_code == 400
    assert '12 horas' in response.text
    assert scalar(seeded, 'SELECT count(*) FROM consumo') == 1
    created = post(client, '/api/consumos', data)
    assert created.status_code == 201
    path = f'/api/consumos/{created.json()["consumo_id"]}'
    assert mutate(client, 'PUT', path, data | {'horas_consumidas': 13}).status_code == 400
    assert client.get(path).json()['horas_consumidas'] == 12
    longer = data | {'fecha_fin': '2026-10-02', 'horas_consumidas': 24}
    assert mutate(client, 'PUT', path, longer).status_code == 200
    assert mutate(client, 'PUT', path, longer | {'fecha_fin': '2026-10-01'}).status_code == 400
