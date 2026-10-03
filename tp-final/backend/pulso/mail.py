"""Consumption notifications. Only plain values leave the request's database session."""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import Settings

logger = logging.getLogger('pulso.mail')


def send_consumption_email(settings: Settings, recipients: list[str], body: str, identifier: int):
    return send_email(
        settings, recipients, f'Pulso: nuevo consumo #{identifier}', body, f'Consumo {identifier}'
    )


def send_email(settings: Settings, recipients: list[str], subject: str, body: str, context: str) -> bool:
    if not recipients:
        logger.warning('%s: sin destinatarios con email.', context)
        return False
    try:
        message = EmailMessage()
        message['Subject'] = subject.replace('\r', ' ').replace('\n', ' ')
        message['From'] = settings.smtp_from
        message['To'] = ', '.join(recipients)
        message.set_content(body)
        transport = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
        options = {'timeout': settings.smtp_timeout}
        if settings.smtp_ssl:
            options['context'] = ssl.create_default_context()
        with transport(settings.smtp_host, settings.smtp_port, **options) as smtp:
            if settings.smtp_starttls and not settings.smtp_ssl:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            refused = smtp.send_message(message)
            if refused:
                logger.warning('%s: SMTP rechazó %s destinatarios.', context, len(refused))
                return False
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        # Do not log credentials or turn a successfully saved consumption into an API error.
        logger.error('%s: no se pudo enviar la notificación SMTP.', context)
        return False
