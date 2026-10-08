from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

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
    login(client)
    content = xlsx_bytes(
        [
            [
                'proyecto_nombre',
                'fecha_inicio',
                'fecha_fin',
                'horas_requeridas',
                'owner_id',
                'proyect_status',
            ],
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


def test_proyectos_admin_only(client, seeded):
    login(client, 'ana', 'Personal123')
    assert upload(client, 'proyectos', 'p.csv', PROYECTOS).status_code == 403


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


def test_tareas_owner_preview_writes_nothing(client, seeded):
    login(client, 'ana', 'Personal123')
    assert summary(upload(client, 'tareas', 't.csv', TAREAS)) == (2, 2, 0, 0, False)
    assert scalar(seeded, 'SELECT count(*) FROM tarea') == 0


def test_tareas_non_owner_gets_row_errors_but_admin_may(client, seeded):
    login(client, 'bruno', 'Personal123')
    body = upload(client, 'tareas', 't.csv', TAREAS).json()
    assert (body['validas'], body['errores_total']) == (0, 2)
    assert 'responsable' in body['errores'][0]['mensaje']
    login(client)
    assert summary(upload(client, 'tareas', 't.csv', TAREAS, confirmar=True)) == (2, 2, 0, 2, True)


def test_tareas_dates_outside_project_unknown_and_ambiguous_project(client, seeded):
    with seeded.state.engine.begin() as connection:
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


def test_tareas_bad_date_order_and_unknown_resource_reported_together(client, seeded):
    login(client)
    content = (
        'proyecto,tarea_nombre,fecha_inicio,fecha_fin,recurso\n'
        'Proyecto ejemplo,Mal,2026-09-10,2026-09-02,fantasma\n'
    )
    body = upload(client, 'tareas', 't.csv', content).json()
    assert body['errores_total'] == 2  # one entry per problem, both on fila 2
    assert {e['fila'] for e in body['errores']} == {2}
    texts = ' | '.join(e['mensaje'] for e in body['errores'])
    assert 'fantasma' in texts
    assert 'fecha' in texts.lower()


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
OWN_HEADER = 'proyecto,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\n'


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
    own = OWN_HEADER + 'Proyecto ejemplo,Analista,2026-10-01,2026-10-01,2,Uno\n'
    assert summary(upload(client, 'consumos', 'c.csv', own, confirmar=True)) == (1, 1, 0, 1, True)
    assert scalar(seeded, "SELECT recurso_id FROM consumo WHERE tarea='Uno'") == 2
    other = (
        'proyecto,recurso,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\n'
        'Proyecto ejemplo,bruno,Analista,2026-10-01,2026-10-01,2,Dos\n'
    )
    body = upload(client, 'consumos', 'c.csv', other).json()
    assert body['errores'][0]['campo'] == 'recurso' and body['validas'] == 0


def test_consumos_plain_user_recurso_id_of_someone_else_is_a_row_error(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    content = (
        'proyecto,recurso_id,rol,fecha_inicio,fecha_fin,horas_consumidas,tarea\n'
        'Proyecto ejemplo,3,Analista,2026-10-01,2026-10-01,2,Dos\n'
    )
    body = upload(client, 'consumos', 'c.csv', content).json()
    # the preparer reports it on the generic 'recurso' column, whichever column carried the reference
    assert [(e['fila'], e['campo']) for e in body['errores']] == [(2, 'recurso')]


def test_consumos_admin_must_name_the_resource(client, seeded, smtp):
    login(client)
    content = OWN_HEADER + 'Proyecto ejemplo,Analista,2026-10-01,2026-10-01,2,Uno\n'
    assert upload(client, 'consumos', 'c.csv', content).json()['errores'][0]['campo'] == 'recurso'


def test_consumos_reuploading_the_same_file_warns_about_duplicates(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    row = OWN_HEADER + 'Proyecto ejemplo,Analista,2026-09-02,2026-09-02,3,diseño\n'
    first = upload(client, 'consumos', 'c.csv', row).json()  # equals the seeded consumption
    assert (first['validas'], first['errores_total'], len(first['advertencias'])) == (1, 0, 1)
    twice = (
        row
        + 'Proyecto ejemplo,Analista,2026-10-05,2026-10-05,1,Nuevo\n'
        + 'Proyecto ejemplo,Analista,2026-10-05,2026-10-05,1,nuevo\n'
    )
    again = upload(client, 'consumos', 'c.csv', twice).json()
    assert len(again['advertencias']) == 2  # seeded duplicate + repeated row inside the file
    assert again['advertencias'][0]['fila'] == 2 and again['validas'] == 3


def test_consumos_twelve_hours_per_day_rule_and_unknown_role(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    content = (
        OWN_HEADER
        + 'Proyecto ejemplo,Analista,2026-10-01,2026-10-01,13,Mucho\n'
        + 'Proyecto ejemplo,Inexistente,2026-10-01,2026-10-01,2,Rol\n'
    )
    body = upload(client, 'consumos', 'c.csv', content).json()
    assert 'no pueden superar 12' in body['errores'][0]['mensaje']
    assert body['errores'][1]['campo'] == 'rol'


def test_consumos_row_with_several_problems_reports_all_on_the_same_row(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    content = OWN_HEADER + 'Proyecto ejemplo,Inexistente,2026-10-01,2026-10-01,13,Mucho\n'
    body = upload(client, 'consumos', 'c.csv', content).json()
    assert body['errores_total'] == 2
    assert {e['fila'] for e in body['errores']} == {2}
    assert 'rol' in {e['campo'] for e in body['errores']}
    assert any('no pueden superar 12' in e['mensaje'] for e in body['errores'])


def test_consumos_non_admin_confirm_with_a_row_error_changes_nothing(client, seeded, smtp):
    login(client, 'ana', 'Personal123')
    content = (
        OWN_HEADER
        + 'Proyecto ejemplo,Analista,2026-10-01,2026-10-01,2,Uno\n'
        + 'Proyecto ejemplo,Inexistente,2026-10-01,2026-10-01,2,Rol\n'
    )
    body = upload(client, 'consumos', 'c.csv', content, confirmar=True).json()
    assert (body['creadas'], body['confirmada'], body['errores_total']) == (0, False, 1)
    assert scalar(seeded, 'SELECT count(*) FROM consumo') == 1
    smtp.assert_not_called()


def add_project(seeded, name):
    with seeded.state.engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO proyecto (proyecto_nombre,fecha_inicio,fecha_fin,horas_requeridas,owner_id,
                proyect_status,porcentaje_avance)
                VALUES (:n,'2026-09-01','2026-09-30',10,2,'En curso',0)"""
            ),
            {'n': name},
        )


def test_tareas_name_and_id_must_agree_when_both_are_given(client, seeded):
    add_project(seeded, 'Otro')
    login(client)
    content = (
        'proyecto,proyecto_id,tarea_nombre,fecha_inicio,fecha_fin\n'
        'Otro,1,Cruzada,2026-09-02,2026-09-03\n'  # name of project 2, id of project 1
        'Fantasma,1,Inexistente,2026-09-02,2026-09-03\n'
        'proyecto EJEMPLO,1,Coincide,2026-09-02,2026-09-03\n'
    )
    body = upload(client, 'tareas', 't.csv', content).json()
    assert [(e['fila'], e['campo']) for e in body['errores']] == [(2, 'proyecto'), (3, 'proyecto')]
    assert (
        'no coincide con el id 1' in body['errores'][0]['mensaje']
        and '«Otro»' in body['errores'][0]['mensaje']
    )
    assert body['validas'] == 1


def test_consumos_recurso_and_rol_name_and_id_must_agree(client, seeded, smtp):
    login(client)
    content = (
        'proyecto,recurso,recurso_id,rol,rol_id,fecha_inicio,fecha_fin,horas_consumidas,tarea\n'
        'Proyecto ejemplo,bruno,2,Analista,1,2026-10-01,2026-10-01,2,Uno\n'
        'Proyecto ejemplo,ana,2,Otro rol,1,2026-10-01,2026-10-01,2,Dos\n'
        'Proyecto ejemplo,ana,2,analista,1,2026-10-01,2026-10-01,2,Tres\n'
    )
    body = upload(client, 'consumos', 'c.csv', content).json()
    assert [(e['fila'], e['campo']) for e in body['errores']] == [(2, 'recurso'), (3, 'rol')]
    assert body['validas'] == 1


def test_proyectos_owner_and_owner_id_must_agree_when_both_are_given(client, seeded):
    login(client)
    head = 'proyecto_nombre,fecha_inicio,fecha_fin,horas_requeridas,owner,owner_id,proyect_status\n'
    content = (
        head
        + 'Uno,2026-10-01,2026-10-02,5,bruno,2,En curso\n'
        + 'Dos,2026-10-01,2026-10-02,5,ANA,2,En curso\n'
    )
    body = upload(client, 'proyectos', 'p.csv', content).json()
    assert [(e['fila'], e['campo']) for e in body['errores']] == [(2, 'owner')]
    assert 'no coincide con el id 2' in body['errores'][0]['mensaje'] and body['validas'] == 1


def test_proyectos_warn_about_repeated_names_but_stay_valid(client, seeded):
    login(client)
    head = 'proyecto_nombre,fecha_inicio,fecha_fin,horas_requeridas,owner,proyect_status\n'
    content = (
        head
        + 'proyecto EJEMPLO,2026-10-01,2026-10-02,5,ana,En curso\n'  # already in the database
        + 'Nuevo,2026-10-01,2026-10-02,5,ana,En curso\n'
        + 'nuevo,2026-10-01,2026-10-02,5,ana,En curso\n'  # repeated inside the file
    )
    body = upload(client, 'proyectos', 'p.csv', content).json()
    assert (body['validas'], body['errores_total']) == (3, 0)
    assert [(w['fila'], w['campo']) for w in body['advertencias']] == [
        (2, 'proyecto_nombre'),
        (4, 'proyecto_nombre'),
    ]
    assert 'ambiguas' in body['advertencias'][0]['mensaje']


def test_tareas_warn_about_repeated_names_in_the_same_project(client, seeded):
    add_project(seeded, 'Otro')
    login(client)
    assert upload(client, 'tareas', 't.csv', TAREAS, confirmar=True).json()['creadas'] == 2
    content = (
        'proyecto,tarea_nombre,fecha_inicio,fecha_fin\n'
        'Proyecto ejemplo,diseño,2026-09-02,2026-09-03\n'  # already in the database
        'Proyecto ejemplo,Otra,2026-09-02,2026-09-03\n'
        'Proyecto ejemplo,OTRA,2026-09-02,2026-09-03\n'  # repeated inside the file
        'Otro,Otra,2026-09-02,2026-09-03\n'  # same name, different project: no warning
    )
    body = upload(client, 'tareas', 't.csv', content).json()
    assert (body['validas'], body['errores_total']) == (4, 0)
    assert [(w['fila'], w['campo']) for w in body['advertencias']] == [
        (2, 'tarea_nombre'),
        (4, 'tarea_nombre'),
    ]
    assert 'Se cargará igual' in body['advertencias'][0]['mensaje']
