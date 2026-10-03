from datetime import datetime
from unittest.mock import patch

from sqlalchemy import text

from pulso.alerts import BUENOS_AIRES, check_deadlines
from tests.conftest import login, post, scalar

PATH = '/api/alertas/ejecutar'


def test_manual_permissions(client):
    with patch('pulso.routers.alerts.run_deadline_check') as check:
        assert post(client, PATH).status_code == 401
        login(client, 'ana', 'Personal123')
        assert post(client, PATH).status_code == 403
        login(client)
        assert client.post(PATH, json={}).status_code == 400
        check.assert_not_called()


def test_manual_runs_again_after_daily(client, seeded):
    login(client)
    with seeded.state.engine.begin() as db:
        db.execute(text("UPDATE proyecto SET fecha_inicio='2000-01-01', fecha_fin='2000-01-02'"))
        db.execute(text("UPDATE recurso SET email='owner@example.com' WHERE recurso_id=2"))
    today = datetime.now(BUENOS_AIRES).date()
    with patch('pulso.alerts.send_email', return_value=True) as send:
        check_deadlines(seeded.state.engine, seeded.state.settings, today)
        for _ in range(2):
            response = post(client, PATH)
            assert response.status_code == 200
            assert response.json() == dict(
                fecha=today.isoformat(), vencidos=1, enviados=1, fallidos=0, sin_email=0, en_ejecucion=False
            )
        assert send.call_count == 3
    assert scalar(seeded, 'SELECT count(*) FROM revision_diaria') == 1


def test_manual_reports_failures_and_missing_email(client, seeded):
    login(client)
    with seeded.state.engine.begin() as db:
        db.execute(text("UPDATE proyecto SET fecha_inicio='2000-01-01', fecha_fin='2000-01-02'"))
    assert post(client, PATH).json()['sin_email'] == 1
    with seeded.state.engine.begin() as db:
        db.execute(text("UPDATE recurso SET email='owner@example.com' WHERE recurso_id=2"))
    with patch('pulso.alerts.send_email', return_value=False):
        assert post(client, PATH).json()['fallidos'] == 1
    assert scalar(seeded, 'SELECT count(*) FROM revision_diaria') == 0


def test_manual_concurrent_check(client, seeded):
    login(client)
    with seeded.state.engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock(70451003)'))
        with patch('pulso.alerts.send_email') as send:
            assert post(client, PATH).json()['en_ejecucion'] is True
            send.assert_not_called()
