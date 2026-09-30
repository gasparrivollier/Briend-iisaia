"""Tareas planificadas (Gantt): permisos, validación, reglas de fechas y de borrado."""

from pulso.schemas import OUT_OF_RANGE
from tests.conftest import login, mutate, post, project_data, scalar


def task_data(**changes):
    return (
        dict(
            tarea_nombre='Relevamiento',
            fecha_inicio='2026-09-02',
            fecha_fin='2026-09-10',
            porcentaje_avance='0',
            recurso_id='3',
        )
        | changes
    )


def create_task(client, **changes):
    return post(client, '/api/proyectos/1/tareas', task_data(**changes))


def test_owner_manages_tasks_and_everyone_reads_them(client):
    login(client, 'ana', 'Personal123')  # owner of project 1
    created = create_task(client)
    assert created.status_code == 201
    task = created.json()
    assert task['recurso_nombre'] == 'bruno' and task['porcentaje_avance'] == 0
    create_task(client, tarea_nombre='  Diseño  ', fecha_inicio='2026-09-01', recurso_id='')

    login(client, 'bruno', 'Personal123')  # plain user: read only
    rows = client.get('/api/proyectos/1/tareas').json()
    assert [r['tarea_nombre'] for r in rows] == ['Diseño', 'Relevamiento']  # by start date
    assert rows[0]['recurso_id'] is None and rows[0]['recurso_nombre'] is None
    assert client.get(f'/api/tareas/{task["tarea_id"]}').json()['tarea_nombre'] == 'Relevamiento'

    login(client, 'ana', 'Personal123')
    changed = mutate(client, 'PUT', f'/api/tareas/{task["tarea_id"]}', task_data(porcentaje_avance=60))
    assert changed.status_code == 200 and changed.json()['porcentaje_avance'] == 60
    assert mutate(client, 'DELETE', f'/api/tareas/{task["tarea_id"]}').status_code == 204
    assert scalar(client.app, 'SELECT count(*) FROM tarea') == 1


def test_only_owner_or_admin_edit_and_403_beats_400(client):
    login(client, 'ana', 'Personal123')
    task_id = create_task(client).json()['tarea_id']
    login(client, 'bruno', 'Personal123')
    assert create_task(client).status_code == 403
    assert create_task(client, tarea_nombre='').status_code == 403  # permission before validation
    assert mutate(client, 'PUT', f'/api/tareas/{task_id}', {}).status_code == 403
    assert mutate(client, 'DELETE', f'/api/tareas/{task_id}').status_code == 403
    login(client)  # admin
    assert mutate(client, 'PUT', f'/api/tareas/{task_id}', task_data(tarea_nombre='Admin')).status_code == 200
    assert client.get('/api/proyectos/99/tareas').status_code == 404
    assert post(client, '/api/proyectos/99/tareas', task_data()).status_code == 404
    assert mutate(client, 'PUT', '/api/tareas/99', task_data()).status_code == 404


def test_validation(client):
    login(client)
    cases = [
        (dict(tarea_nombre='   '), 'Completá todos los campos obligatorios.'),
        (dict(porcentaje_avance='101'), OUT_OF_RANGE),
        (dict(porcentaje_avance=True), 'Ingresá valores numéricos válidos.'),
        (dict(fecha_fin='2026-09-01'), 'La fecha de fin no puede ser anterior al inicio.'),
        (dict(fecha_inicio='no'), 'Ingresá fechas válidas.'),
        (dict(recurso_id='abc'), 'Seleccioná una referencia válida.'),
        (dict(recurso_id='99'), 'El recurso, proyecto o rol seleccionado no existe.'),
    ]
    for changes, message in cases:
        response = create_task(client, **changes)
        assert response.status_code == 400, changes
        assert response.json()['error']['message'] == message, changes


def test_task_dates_must_fall_inside_the_project(client):
    login(client)  # project 1 runs 2026-09-01 → 2026-09-30
    for changes in (dict(fecha_inicio='2026-08-31'), dict(fecha_fin='2026-10-01')):
        response = create_task(client, **changes)
        assert response.status_code == 400
        assert response.json()['error']['message'] == (
            'Las fechas de la tarea deben estar dentro de las del proyecto (2026-09-01 → 2026-09-30).'
        )
    assert create_task(client, fecha_inicio='2026-09-01', fecha_fin='2026-09-30').status_code == 201


def test_project_range_cannot_leave_tasks_outside(client):
    login(client)
    create_task(client, fecha_fin='2026-09-20')
    shrunk = mutate(client, 'PUT', '/api/proyectos/1', project_data() | {'fecha_fin': '2026-09-15'})
    assert shrunk.status_code == 400
    assert 'Hay 1 tarea(s) fuera de las nuevas fechas' in shrunk.json()['error']['message']
    assert scalar(client.app, 'SELECT fecha_fin FROM proyecto').isoformat() == '2026-09-30'
    widened = mutate(client, 'PUT', '/api/proyectos/1', project_data() | {'fecha_fin': '2026-10-31'})
    assert widened.status_code == 200


def test_project_with_tasks_cannot_be_deleted(client):
    login(client)
    task_id = create_task(client).json()['tarea_id']
    mutate(client, 'DELETE', '/api/consumos/1')  # the seeded consumption would also block it
    assert mutate(client, 'DELETE', '/api/proyectos/1').status_code == 409
    assert mutate(client, 'DELETE', f'/api/tareas/{task_id}').status_code == 204
    assert mutate(client, 'DELETE', '/api/proyectos/1').status_code == 204
