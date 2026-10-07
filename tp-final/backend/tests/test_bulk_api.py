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
    assert [(e['fila'], e['campo']) for e in body['errores']] == [
        (3, 'rol_descripcion'),
        (4, 'rol_descripcion'),
    ]
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


RECURSOS = (
    'recurso_nombre,email,es_admin,password\ncarla,carla@example.com,si,Secreta123\ndario,,no,Secreta456\n'
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


def test_recursos_single_row_two_problems(client, seeded):
    login(client)
    content = (
        'recurso_nombre,email,es_admin,password\n'
        'ANA,,no,short\n'  # exists AND password too short
    )
    body = upload(client, 'recursos', 'r.csv', content).json()
    errors = body['errores']
    assert len(errors) == 2
    assert errors[0]['fila'] == 2
    assert errors[1]['fila'] == 2
    fields = {e['campo'] for e in errors}
    assert 'password' in fields and 'recurso_nombre' in fields
