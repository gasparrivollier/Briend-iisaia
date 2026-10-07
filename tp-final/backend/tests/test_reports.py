"""Dashboard report: pure calculations (prorating, indices, tasks) and the endpoint."""

from datetime import date

import pytest

from pulso import reports
from pulso.routers.reports import today
from tests.conftest import login, post, project_data

PROJECT = dict(
    fecha_inicio=date(2026, 10, 1),
    fecha_fin=date(2026, 10, 3),
    horas_requeridas=36.0,
    horas_consumidas=0.0,
    saldo=36.0,
    porcentaje_consumo=0.0,
    porcentaje_avance=0.0,
)


def consumption(start, end, hours, role='Dev', resource='ana', task='Tarea'):
    return dict(
        fecha_inicio=start,
        fecha_fin=end,
        horas_consumidas=hours,
        rol_descripcion=role,
        recurso_nombre=resource,
        tarea=task,
    )


def test_daily_hours_matches_the_chart_rule():
    # Same numbers as frontend/tests/unit/projectHours.spec.ts ("distributes overlapping consumptions").
    rows = [
        consumption(date(2026, 10, 1), date(2026, 10, 3), 9),
        consumption(date(2026, 10, 2), date(2026, 10, 2), 5),
    ]
    per_day: dict[date, float] = {}
    for row in rows:
        for day, hours in reports.daily_hours(row):
            per_day[day] = per_day.get(day, 0) + hours
    assert per_day == {date(2026, 10, 1): 3, date(2026, 10, 2): 8, date(2026, 10, 3): 3}


def test_periods_split_across_weeks_and_months_and_fill_gaps():
    # Sun 2026-10-04 .. Mon 2026-10-05: one day in each ISO week.
    weeks = reports.periods([consumption(date(2026, 10, 4), date(2026, 10, 5), 10)], 'semana')
    assert [(w['desde'], w['hasta'], w['horas']) for w in weeks] == [
        (date(2026, 9, 28), date(2026, 10, 4), 5),
        (date(2026, 10, 5), date(2026, 10, 11), 5),
    ]
    months = reports.periods(
        [
            consumption(date(2026, 11, 30), date(2026, 12, 1), 4),
            consumption(date(2027, 2, 1), date(2027, 2, 1), 1),
        ],
        'mes',
    )
    assert [(m['desde'], m['horas']) for m in months] == [
        (date(2026, 11, 1), 2),
        (date(2026, 12, 1), 2),
        (date(2027, 1, 1), 0),
        (date(2027, 2, 1), 1),
    ]
    assert months[1]['hasta'] == date(2026, 12, 31)
    assert reports.periods([], 'mes') == []


def test_health_indices_and_zero_denominators():
    empty = reports.health(PROJECT, date(2026, 9, 1))  # before the start
    assert empty['porcentaje_tiempo'] == 0 and empty['indice_cronograma'] is None
    assert empty['indice_eficiencia'] is None  # nothing consumed yet

    project = PROJECT | dict(horas_consumidas=18.0, porcentaje_consumo=50.0, porcentaje_avance=25.0)
    result = reports.health(project, date(2026, 10, 2))  # 2 of 3 days elapsed
    assert result['horas_ganadas'] == 9
    assert result['indice_eficiencia'] == pytest.approx(0.5) and result['estado_eficiencia'] == 'critico'
    assert result['indice_cronograma'] == pytest.approx(25 / (200 / 3))
    assert reports.index_state(1.0) == 'bien' and reports.index_state(0.9) == 'atencion'
    assert reports.health(project, date(2027, 1, 1))['porcentaje_tiempo'] == 100  # overdue is capped


def test_pace_and_execution():
    rows = [consumption(date(2026, 9, 28), date(2026, 10, 4), 14)]  # 2 h/day
    project = PROJECT | dict(fecha_fin=date(2026, 10, 15), saldo=22.0)
    ritmo = reports.pace(project, rows, date(2026, 10, 1))
    assert ritmo['horas_semana_reciente'] == pytest.approx(8 / 4)  # 4 days up to today = 8 h
    assert ritmo['horas_semana_promedio'] == pytest.approx(8)  # a week minimum
    assert ritmo['horas_semana_necesarias'] == pytest.approx(22 / (14 / 7))
    assert ritmo['dias_restantes'] == 14
    overdue = reports.pace(project, rows, date(2026, 10, 20))
    assert overdue['horas_semana_necesarias'] is None and overdue['dias_restantes'] == 0

    result = reports.execution(PROJECT, rows, date(2026, 10, 2))
    assert result['primer_consumo'] == date(2026, 9, 28) and result['dias_desvio_inicio'] == -3
    assert result['horas_antes_inicio'] == 6 and result['horas_despues_fin'] == 2
    assert result['dias_con_actividad'] == 5 and result['dias_transcurridos'] == 2
    none = reports.execution(PROJECT, [], date(2026, 10, 2))
    assert none['primer_consumo'] is None and none['dias_desvio_inicio'] is None


def task(start, end, progress, resource=1):
    return dict(
        tarea_id=1, tarea_nombre='t', fecha_inicio=start, fecha_fin=end, porcentaje_avance=progress,
        recurso_id=resource, recurso_nombre=None, proyecto_id=1,
    )  # fmt: skip


def test_task_health():
    today = date(2026, 10, 10)
    result = reports.task_health(
        [
            task(date(2026, 10, 1), date(2026, 10, 5), 40),  # overdue
            task(date(2026, 10, 1), date(2026, 10, 3), 100),  # done
            task(date(2026, 10, 8), date(2026, 10, 20), 0, None),  # should have started, unassigned
            task(date(2026, 10, 9), date(2026, 10, 12), 50),  # running
            task(date(2026, 10, 20), date(2026, 10, 25), 0),  # future
        ],
        today,
    )
    assert (result['total'], result['completadas'], result['en_curso'], result['sin_recurso']) == (5, 1, 2, 1)
    assert len(result['vencidas']) == 1 and len(result['sin_iniciar_atrasadas']) == 1
    assert 0 < result['avance_real'] < result['avance_planificado'] <= 100
    assert reports.task_health([], today)['avance_planificado'] == 0


def test_distribution_groups_activities_and_caps_the_list():
    rows = [consumption(date(2026, 10, 1), date(2026, 10, 1), 1, task=f'Act {i}') for i in range(10)]
    rows += [consumption(date(2026, 10, 1), date(2026, 10, 1), 5, task=' diseño '), consumption(
        date(2026, 10, 1), date(2026, 10, 1), 5, task='Diseño', role='QA', resource='bruno')]  # fmt: skip
    result = reports.distribution(rows)
    names = [a['nombre'] for a in result['actividades']]
    assert names[0] == 'diseño' and len(names) == reports.TOP_ACTIVITIES + 1 and names[-1] == 'Otras'
    assert sum(a['porcentaje'] for a in result['actividades']) == pytest.approx(100)
    assert {r['nombre'] for r in result['por_rol']} == {'Dev', 'QA'}


def test_endpoint(client):
    assert client.get('/api/proyectos/1/reporte').status_code == 401
    login(client, 'bruno', 'Personal123')  # any logged-in user can read
    client.app.dependency_overrides[today] = lambda: date(2026, 9, 15)
    try:
        body = client.get('/api/proyectos/1/reporte').json()
        assert body['fecha_corte'] == '2026-09-15' and body['periodo'] == 'semana'
        assert body['salud']['porcentaje_tiempo'] == pytest.approx(15 / 30 * 100)
        assert body['salud']['indice_eficiencia'] == pytest.approx(2.5 / 3)
        assert body['periodos'][0]['por_rol'] == {'Analista': 3}
        assert body['tareas']['total'] == 0 and body['ejecucion']['primer_consumo'] == '2026-09-02'
        assert body['distribucion']['por_recurso'][0]['nombre'] == 'ana'
        monthly = client.get('/api/proyectos/1/reporte?periodo=mes').json()
        assert [p['horas'] for p in monthly['periodos']] == [3]
    finally:
        client.app.dependency_overrides.clear()


def test_endpoint_errors(client):
    login(client)
    assert client.get('/api/proyectos/1/reporte?periodo=anio').status_code == 400
    assert client.get('/api/proyectos/99/reporte').status_code == 404


def test_endpoint_empty_project(client):
    login(client)
    body = post(
        client,
        '/api/proyectos',
        project_data() | dict(proyecto_nombre='Vacío', fecha_inicio='2026-10-01', fecha_fin='2026-10-31'),
    ).json()
    report = client.get(f'/api/proyectos/{body["proyecto_id"]}/reporte').json()
    assert report['periodos'] == [] and report['ejecucion']['primer_consumo'] is None
    assert report['salud']['indice_eficiencia'] is None
