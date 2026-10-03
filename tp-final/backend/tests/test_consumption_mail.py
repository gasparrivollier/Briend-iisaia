import smtplib
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from pulso.config import Settings
from pulso.mail import send_consumption_email

from .conftest import consumption_data, login, mutate, post, scalar


@pytest.fixture
def smtp(monkeypatch):
    transport = MagicMock()
    transport.return_value.__enter__.return_value.send_message.return_value = {}
    monkeypatch.setattr('pulso.mail.smtplib.SMTP', transport)
    return transport


@pytest.mark.parametrize(
    'owner_email,resource_email,count',
    [
        ('ana@example.com', 'bruno@example.com', 2),
        ('igual@example.com', 'IGUAL@example.com', 1),
        (None, 'bruno@example.com', 1),
        (None, None, 0),
    ],
)
def test_create_notifies(client, seeded, smtp, owner_email, resource_email, count):
    with seeded.state.engine.begin() as connection:
        connection.execute(text('UPDATE recurso SET email=:email WHERE recurso_id=2'), {'email': owner_email})
        connection.execute(
            text('UPDATE recurso SET email=:email WHERE recurso_id=3'), {'email': resource_email}
        )
    login(client)
    data = consumption_data() | {'recurso_id': 3, 'horas_consumidas': 2}
    response = post(client, '/api/consumos', data)
    assert response.status_code == 201
    sender = smtp.return_value.__enter__.return_value.send_message
    if count:
        sender.assert_called_once()
        message = sender.call_args.args[0]
        assert len(message['To'].addresses) == count
        body = message.get_content()
        for expected in (
            'Proyecto ejemplo',
            'bruno',
            'Analista',
            '01/10/2026',
            '02/10/2026',
            'Horas consumidas: 2',
        ):
            assert expected in body
    else:
        smtp.assert_not_called()
    sender.reset_mock()
    assert mutate(client, 'PUT', f'/api/consumos/{response.json()["consumo_id"]}', data).status_code == 200
    sender.assert_not_called()


def test_failure_preserves_consumption(client, seeded, smtp, caplog):
    with seeded.state.engine.begin() as connection:
        connection.execute(text("UPDATE recurso SET email='ana@example.com' WHERE recurso_id=2"))
    smtp.side_effect = smtplib.SMTPException('unavailable')
    login(client)
    assert post(client, '/api/consumos', consumption_data()).status_code == 201
    assert scalar(seeded, 'SELECT count(*) FROM consumo') == 2
    assert 'no se pudo enviar' in caplog.text


def test_invalid_consumption_does_not_send(client, smtp):
    login(client)
    assert post(client, '/api/consumos', consumption_data() | {'rol_id': 999}).status_code == 400
    smtp.assert_not_called()


def test_session_resource_used(client, seeded, smtp):
    with seeded.state.engine.begin() as connection:
        connection.execute(text("UPDATE recurso SET email='ana@example.com' WHERE recurso_id=2"))
    login(client, 'ana', 'Personal123')
    response = post(client, '/api/consumos', consumption_data() | {'recurso_id': 3, 'horas_consumidas': 2})
    assert response.status_code == 201
    message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    assert 'Recurso: ana' in message.get_content()
    assert str(message['To']) == 'ana@example.com'


def test_smtp_tls_and_auth(smtp):
    settings = Settings(smtp_starttls=True, smtp_username='user', smtp_password='secret')
    send_consumption_email(settings, ['ana@example.com'], 'Detalle', 1)
    connection = smtp.return_value.__enter__.return_value
    connection.starttls.assert_called_once()
    connection.login.assert_called_once_with('user', 'secret')
