"""Port of the Flask suite (tests/test_app.py): same contract, now against FastAPI + Postgres."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from pulso.cli import init_db
from pulso.security import verify_password
from tests.conftest import consumption_data, login, mutate, post, project_data, scalar


def test_login_csrf_logout(client):
    assert client.get('/api/proyectos').status_code == 401
    session = client.get('/api/session').json()
    assert session['user'] is None and session['csrf_token']
    assert (
        client.post('/api/login', json={'recurso_nombre': 'admin', 'password': 'Proyecto1'}).status_code
        == 400
    )
    assert login(client, password='incorrecta').status_code == 401
    result = login(client)
    assert result.status_code == 200 and result.json()['user']['es_admin'] is True
    assert result.json()['csrf_token'] != session['csrf_token']
    assert client.get('/api/proyectos').status_code == 200
    assert post(client, '/api/logout').json()['user'] is None
    assert client.get('/api/proyectos').status_code == 401


def test_session_cookie_flags(client):
    cookie = client.get('/api/session').headers['set-cookie'].lower()
    assert 'pulso_session=' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie


def test_login_is_case_insensitive(client):
    assert login(client, 'ANA', 'Personal123').status_code == 200


def test_initialization_password_and_existing_database(app):
    url = app.state.settings.database_url
    assert init_db(url) is True
    client = TestClient(app)
    assert login(client).json()['user']['debe_cambiar_password'] is True
    blocked = client.get('/api/roles')
    assert blocked.status_code == 403 and blocked.json()['error']['code'] == 'password_change_required'
    assert post(client, '/api/roles', {'rol_descripcion': 'No permitido'}).status_code == 403
    for data in [
        dict(actual='wrong', password='Distinta123', confirmacion='Distinta123'),
        dict(actual='Proyecto1', password='Proyecto1', confirmacion='Proyecto1'),
        dict(actual='Proyecto1', password='short', confirmacion='short'),
        dict(actual='Proyecto1', password='Distinta123', confirmacion='Otra123'),
    ]:
        assert mutate(client, 'PUT', '/api/password', data).status_code == 400
    result = mutate(
        client,
        'PUT',
        '/api/password',
        dict(actual='Proyecto1', password='Distinta123', confirmacion='Distinta123'),
    )
    assert result.status_code == 200 and result.json()['user']['debe_cambiar_password'] is False
    stored = scalar(app, 'SELECT password FROM recurso')
    assert verify_password('Distinta123', stored)[0]
    assert init_db(url) is False  # idempotent: never recreates or resets accounts
    assert scalar(app, 'SELECT password FROM recurso') == stored
    assert login(TestClient(app), password='Distinta123').status_code == 200


def test_password_change_closes_other_sessions(client, seeded):
    other = TestClient(seeded)
    login(other, 'ana', 'Personal123')
    login(client, 'ana', 'Personal123')
    data = dict(actual='Personal123', password='Nueva12345', confirmacion='Nueva12345')
    assert mutate(client, 'PUT', '/api/password', data).status_code == 200
    assert client.get('/api/proyectos').status_code == 200
    assert other.get('/api/proyectos').status_code == 401


def test_legacy_werkzeug_hash_is_accepted_and_upgraded(client, seeded):
    with seeded.state.engine.begin() as connection:
        connection.execute(
            text("UPDATE recurso SET password=:p WHERE recurso_nombre='ana'"),
            {'p': generate_password_hash('Personal123')},
        )
    assert login(client, 'ana', 'Personal123').status_code == 200
    assert scalar(seeded, "SELECT password FROM recurso WHERE recurso_nombre='ana'").startswith('$argon2')


@pytest.mark.parametrize('path', ['/api/recursos', '/api/roles', '/api/recursos/1', '/api/roles/1'])
def test_admin_read_permissions(client, path):
    login(client, 'bruno', 'Personal123')
    assert client.get(path).status_code == 403
    # Non-sensitive catalogs remain available to register hours and filter projects.
    assert client.get('/api/catalogos').status_code == 200


@pytest.mark.parametrize(
    'method,path',
    [
        ('POST', '/api/proyectos'), ('POST', '/api/recursos'), ('POST', '/api/roles'),
        ('PUT', '/api/proyectos/1'), ('PUT', '/api/consumos/1'), ('PUT', '/api/recursos/2'),
        ('PUT', '/api/roles/1'), ('DELETE', '/api/proyectos/1'), ('DELETE', '/api/consumos/1'),
        ('DELETE', '/api/recursos/2'), ('DELETE', '/api/roles/1'),
    ],
)  # fmt: skip
def test_direct_mutation_permissions(client, method, path):
    login(client, 'bruno', 'Personal123')
    assert mutate(client, method, path, consumption_data()).status_code == 403


def test_owner_cannot_reassign_project(client, seeded):
    login(client, 'ana', 'Personal123')
    data = project_data()
    data.update(owner_id=3, porcentaje_avance=70)
    assert mutate(client, 'PUT', '/api/proyectos/1', data).status_code == 200
    assert scalar(seeded, 'SELECT owner_id FROM proyecto') == 2
    assert scalar(seeded, 'SELECT porcentaje_avance FROM proyecto') == 70


def test_consumption_owner_totals_and_manual_progress(client):
    login(client, 'bruno', 'Personal123')
    result = post(client, '/api/consumos', consumption_data())
    assert result.status_code == 201 and result.json()['recurso_id'] == 3
    detail = client.get('/api/proyectos/1').json()
    p = detail['proyecto']
    assert p['horas_consumidas'] == 15 and p['porcentaje_consumo'] == 150
    assert p['saldo'] == -5 and p['exceso'] == 5 and p['porcentaje_avance'] == 25
    assert detail['por_recurso'] == {'ana': 3, 'bruno': 12} and detail['por_rol'] == {'Analista': 15}
    data = consumption_data()
    data['horas_consumidas'] = 5
    assert mutate(client, 'PUT', '/api/consumos/2', data).status_code == 200
    assert client.get('/api/proyectos/1').json()['proyecto']['horas_consumidas'] == 8
    assert mutate(client, 'DELETE', '/api/consumos/2').status_code == 204
    assert client.get('/api/proyectos/1').json()['proyecto']['horas_consumidas'] == 3
    assert client.get('/api/proyectos/1').json()['proyecto']['porcentaje_avance'] == 25


@pytest.mark.parametrize(
    'name,value',
    [
        ('horas_requeridas', 0), ('horas_requeridas', -1), ('horas_requeridas', 'nan'),
        ('horas_requeridas', 'inf'), ('horas_requeridas', True), ('horas_requeridas', []),
        ('porcentaje_avance', -1), ('porcentaje_avance', 101), ('porcentaje_avance', 'nan'),
        ('fecha_fin', '2026-08-01'), ('fecha_inicio', '2026-02-30'), ('owner_id', 999),
        ('owner_id', 2.5), ('owner_id', True), ('proyecto_nombre', '  '), ('proyecto_nombre', None),
        ('proyecto_nombre', {}), ('proyect_status', 'inventado'),
    ],
)  # fmt: skip
def test_project_validation(client, seeded, name, value):
    login(client)
    data = project_data()
    data[name] = value
    response = mutate(client, 'PUT', '/api/proyectos/1', data)
    assert response.status_code == 400 and response.json()['error']['message']
    assert scalar(seeded, 'SELECT proyecto_nombre FROM proyecto') == 'Proyecto ejemplo'


def test_validation_messages_are_spanish(client):
    login(client)
    data = project_data()
    del data['horas_requeridas']
    assert mutate(client, 'PUT', '/api/proyectos/1', data).json()['error']['message'] == (
        'Ingresá valores numéricos válidos.'
    )
    data = project_data()
    data['fecha_fin'] = '2026-08-01'
    assert mutate(client, 'PUT', '/api/proyectos/1', data).json()['error']['message'] == (
        'La fecha de fin no puede ser anterior al inicio.'
    )


@pytest.mark.parametrize('value', [0, 100])
def test_progress_boundaries(client, value):
    login(client)
    data = project_data()
    data['porcentaje_avance'] = value
    response = mutate(client, 'PUT', '/api/proyectos/1', data)
    assert response.status_code == 200 and response.json()['porcentaje_avance'] == value


@pytest.mark.parametrize(
    'name,value',
    [
        ('horas_consumidas', 0), ('horas_consumidas', -2), ('horas_consumidas', 'nan'),
        ('fecha_fin', '2026-01-01'), ('fecha_inicio', 'bad'), ('proyecto_id', 999),
        ('recurso_id', 999), ('rol_id', 999), ('tarea', ' '), ('tarea', []),
    ],
)  # fmt: skip
def test_consumption_validation(client, seeded, name, value):
    login(client)
    data = consumption_data()
    data[name] = value
    assert post(client, '/api/consumos', data).status_code == 400
    assert scalar(seeded, 'SELECT COUNT(*) FROM consumo') == 1


@pytest.mark.parametrize('path', ['/api/proyectos/1', '/api/recursos/2', '/api/roles/1'])
def test_referenced_deletion_blocked(client, path):
    login(client)
    response = mutate(client, 'DELETE', path)
    assert response.status_code == 409 and response.json()['error']['code'] == 'conflict'
    assert client.get(path).status_code == 200


def test_last_admin_duplicates_and_boolean_validation(client):
    login(client)
    assert mutate(client, 'DELETE', '/api/recursos/1').json()['error']['code'] == 'last_admin'
    assert (
        mutate(client, 'PUT', '/api/recursos/1', {'recurso_nombre': 'admin', 'es_admin': False}).status_code
        == 409
    )
    assert (
        post(client, '/api/recursos', {'recurso_nombre': 'ANA', 'password': 'Personal123'}).status_code == 409
    )
    assert post(client, '/api/roles', {'rol_descripcion': 'Analista'}).status_code == 409
    assert (
        mutate(client, 'PUT', '/api/recursos/2', {'recurso_nombre': 'ana', 'es_admin': 'false'}).status_code
        == 400
    )
    assert client.get('/api/recursos/1').json()['es_admin'] is True


def test_admin_crud_and_reset(client, seeded):
    login(client)
    assert (
        post(client, '/api/recursos', {'recurso_nombre': 'nuevo', 'password': 'Inicial123'}).status_code
        == 201
    )
    result = mutate(
        client, 'PUT', '/api/recursos/4', {'recurso_nombre': 'renombrado', 'password': 'Reinicio123'}
    )
    assert result.status_code == 200 and result.json()['debe_cambiar_password'] is True
    assert verify_password('Reinicio123', scalar(seeded, 'SELECT password FROM recurso WHERE recurso_id=4'))[
        0
    ]
    assert post(client, '/api/roles', {'rol_descripcion': 'Diseñador'}).status_code == 201
    assert mutate(client, 'PUT', '/api/roles/2', {'rol_descripcion': 'Desarrollador'}).status_code == 200
    assert post(client, '/api/proyectos', project_data()).status_code == 201
    assert mutate(client, 'DELETE', '/api/proyectos/2').status_code == 204
    assert mutate(client, 'DELETE', '/api/roles/2').status_code == 204
    assert mutate(client, 'DELETE', '/api/recursos/4').status_code == 204
    assert client.get('/api/recursos/4').status_code == 404


def test_filters_read_views_and_api_only(client):
    login(client)
    for path in [
        '/api/proyectos', '/api/proyectos/1', '/api/consumos', '/api/consumos/1', '/api/roles',
        '/api/roles/1', '/api/recursos', '/api/recursos/1', '/api/catalogos', '/api/session',
    ]:  # fmt: skip
        response = client.get(path)
        assert response.status_code == 200 and response.headers['content-type'] == 'application/json', path
    assert len(client.get('/api/proyectos?estado=En+curso&responsable=2').json()) == 1
    assert client.get('/api/proyectos?estado=finalizado').json() == []
    assert client.get('/api/proyectos?responsable=3').json() == []
    assert client.get('/api/proyectos?responsable=abc').status_code == 400
    assert client.get('/api/proyectos/999').status_code == 404
    assert client.get('/api/roles/abc').status_code == 404
    assert client.get('/api/logout').status_code == 405
    assert client.get('/api/unknown').json()['error']['code'] == 'http_404'
    assert client.get('/proyectos').status_code == 404  # No server-rendered pages.


def test_catalogs_sorted_case_insensitive(client, seeded):
    login(client)
    post(client, '/api/recursos', {'recurso_nombre': 'Zoe', 'password': 'Inicial123'})
    post(client, '/api/recursos', {'recurso_nombre': 'beto', 'password': 'Inicial123'})
    names = [r['recurso_nombre'] for r in client.get('/api/catalogos').json()['recursos']]
    assert names == ['admin', 'ana', 'beto', 'bruno', 'Zoe']


def test_foreign_keys(seeded):
    with pytest.raises(IntegrityError), seeded.state.engine.begin() as connection:
        connection.execute(text('DELETE FROM rol WHERE rol_id=1'))


def test_deleted_account_id_is_not_reused(client):
    login(client)
    first = post(client, '/api/recursos', {'recurso_nombre': 'temporal', 'password': 'Inicial123'}).json()
    mutate(client, 'DELETE', '/api/recursos/' + str(first['recurso_id']))
    second = post(client, '/api/recursos', {'recurso_nombre': 'distinto', 'password': 'Inicial123'}).json()
    assert second['recurso_id'] > first['recurso_id']


def test_password_hashes_never_exposed(client, seeded):
    login(client)
    with seeded.state.engine.connect() as connection:
        hashes = [row[0] for row in connection.execute(text('SELECT password FROM recurso'))]
    for path in ['/api/session', '/api/recursos', '/api/recursos/1', '/api/catalogos', '/api/proyectos/1']:
        body = client.get(path).text
        assert all(value not in body for value in hashes)
        assert '"password"' not in body


@pytest.mark.parametrize(
    'method,path', [('POST', '/api/roles'), ('PUT', '/api/proyectos/1'), ('DELETE', '/api/consumos/1')]
)
def test_csrf_all_mutation_methods(client, method, path):
    login(client)
    response = client.request(method, path, json={})
    assert response.status_code == 400 and response.json()['error']['code'] == 'csrf_invalid'


@pytest.mark.parametrize('payload', [[], None, 'text', 123])
def test_non_object_json(client, payload):
    login(client)
    token = client.get('/api/session').json()['csrf_token']
    response = client.post(
        '/api/roles',
        content=json.dumps(payload),
        headers={'X-CSRF-Token': token, 'Content-Type': 'application/json'},
    )
    assert response.status_code == 400 and response.json()['error']


def test_invalid_json_content_type_and_size(client):
    login(client)
    token = client.get('/api/session').json()['csrf_token']
    headers = {'X-CSRF-Token': token}
    bad = client.post('/api/roles', content='{bad', headers=headers | {'Content-Type': 'application/json'})
    assert bad.status_code == 400 and bad.json()['error']
    assert client.post('/api/roles', data={'rol_descripcion': 'X'}, headers=headers).status_code == 415
    huge = client.post('/api/roles', json={'rol_descripcion': 'x' * (1024 * 1024 + 1)}, headers=headers)
    assert huge.status_code == 413 and huge.json()['error']['code'] == 'http_413'


def test_unhandled_errors_are_json(seeded):
    @seeded.get('/api/boom')
    def boom():
        raise RuntimeError('boom')

    response = TestClient(seeded, raise_server_exceptions=False).get('/api/boom')
    assert response.status_code == 500
    assert response.json() == {'error': {'code': 'http_500', 'message': 'Error interno del servidor.'}}
