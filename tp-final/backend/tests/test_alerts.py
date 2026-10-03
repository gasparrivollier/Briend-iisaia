from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from pulso.alerts import check_deadlines
from tests.conftest import consumption_data, login, mutate, post, scalar


@pytest.fixture
def sender(monkeypatch, seeded):
    smtp = MagicMock()
    smtp.return_value.__enter__.return_value.send_message.return_value = {}
    monkeypatch.setattr('pulso.mail.smtplib.SMTP', smtp)
    with seeded.state.engine.begin() as db:
        db.execute(text("UPDATE recurso SET email='owner@example.com' WHERE recurso_id=2"))
    return smtp.return_value.__enter__.return_value.send_message


def test_daily_deadline_and_restart(seeded, sender):
    engine, settings = seeded.state.engine, seeded.state.settings
    assert check_deadlines(engine, settings, date(2026, 9, 29)) == 0
    assert check_deadlines(engine, settings, date(2026, 9, 30)) == 0
    assert check_deadlines(engine, settings, date(2026, 10, 1)) == 1
    message = sender.call_args.args[0]
    assert str(message['Subject']) == 'URGENTE Fecha de finalizacion excedida Proyecto ejemplo'
    assert str(message['To']) == 'owner@example.com'
    assert '01/10/2026' in message.get_content()
    assert '30/09/2026' in message.get_content()
    assert check_deadlines(engine, settings, date(2026, 10, 1)) == 0
    sender.assert_called_once()
    assert check_deadlines(engine, settings, date(2026, 10, 2)) == 1
    assert scalar(seeded, 'SELECT porcentaje_avance FROM proyecto WHERE proyecto_id=1') == 25


def test_no_owner_email(seeded, sender):
    with seeded.state.engine.begin() as db:
        db.execute(text('UPDATE recurso SET email=NULL'))
    assert check_deadlines(seeded.state.engine, seeded.state.settings, date(2026, 10, 1)) == 0
    sender.assert_not_called()


def test_hours_crossing_and_edit(client, seeded, sender):
    login(client)
    data = consumption_data() | {'horas_consumidas': 7}
    created = post(client, '/api/consumos', data)
    assert created.status_code == 201  # Existing 3 + 7 == required 10: no urgent alert.
    assert sender.call_count == 1
    sender.reset_mock()
    path = f'/api/consumos/{created.json()["consumo_id"]}'
    assert mutate(client, 'PUT', path, data | {'horas_consumidas': 8}).status_code == 200
    sender.assert_called_once()
    message = sender.call_args.args[0]
    assert str(message['Subject']) == 'URGENTE horas aplicadas excedidas Proyecto ejemplo'
    assert str(message['To']) == 'owner@example.com'
    assert 'Horas requeridas: 10' in message.get_content()
    assert 'Horas aplicadas: 11' in message.get_content()
    sender.reset_mock()
    assert post(client, '/api/consumos', data).status_code == 201
    assert sender.call_count == 1  # Only the normal consumption notification while already over budget.
    assert scalar(seeded, 'SELECT porcentaje_avance FROM proyecto WHERE proyecto_id=1') == 25


def test_hours_crossing_on_create(client, sender):
    login(client)
    assert post(client, '/api/consumos', consumption_data()).status_code == 201
    messages = [call.args[0] for call in sender.call_args_list]
    urgent = [message for message in messages if str(message['Subject']).startswith('URGENTE')]
    assert len(urgent) == 1
    assert 'Horas aplicadas: 15' in urgent[0].get_content()


def test_daily_smtp_failure_recorded(seeded, sender):
    sender.side_effect = OSError('offline')
    assert check_deadlines(seeded.state.engine, seeded.state.settings, date(2026, 10, 1)) == 0
    assert scalar(seeded, 'SELECT count(*) FROM revision_diaria') == 1
