"""Each test session runs against a throwaway Postgres database migrated with Alembic.

Requires a reachable Postgres (dev: `podman compose up -d db` from tp-final/). Override the
server with TEST_DATABASE_URL (a URL whose user can CREATE/DROP DATABASE).
"""

import io
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from pulso.cli import seed
from pulso.config import Settings
from pulso.main import create_app
from pulso.security import hash_password

SERVER_URL = os.environ.get('TEST_DATABASE_URL', 'postgresql+psycopg://pulso:pulso@localhost:5432/pulso')
ALEMBIC_INI = os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')


def alembic_config(url: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.attributes['database_url'] = url
    config.attributes['configure_logger'] = False
    return config


@pytest.fixture(scope='session')
def database_url():
    name = f'pulso_test_{uuid.uuid4().hex[:8]}'
    admin = create_engine(SERVER_URL, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE {name}'))
    url = make_url(SERVER_URL).set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(scope='session')
def migrated(database_url):
    command.upgrade(alembic_config(database_url), 'head')
    return database_url


@pytest.fixture
def app(migrated):
    app = create_app(Settings(database_url=migrated))
    yield app
    with app.state.engine.begin() as connection:
        tables = ', '.join(['revision_diaria', 'consumo', 'tarea', 'proyecto', 'rol', 'sesion', 'recurso'])
        connection.execute(text(f'TRUNCATE {tables} RESTART IDENTITY CASCADE'))
    app.state.engine.dispose()


@pytest.fixture
def seeded(app):
    """Same fixture data as the Flask suite: admin(1), ana(2), bruno(3), one project owned by ana."""
    seed(app.state.engine)
    personal = hash_password('Personal123')
    with app.state.engine.begin() as connection:
        connection.execute(text('UPDATE recurso SET debe_cambiar_password=false WHERE recurso_id=1'))
        for name in ('ana', 'bruno'):
            connection.execute(
                text(
                    'INSERT INTO recurso (recurso_nombre,password,debe_cambiar_password) VALUES (:n,:p,false)'
                ),
                {'n': name, 'p': personal},
            )
        connection.execute(text("INSERT INTO rol (rol_descripcion) VALUES ('Analista')"))
        connection.execute(
            text(
                """INSERT INTO proyecto (proyecto_nombre,fecha_inicio,fecha_fin,horas_requeridas,owner_id,
                proyect_status,porcentaje_avance)
                VALUES ('Proyecto ejemplo','2026-09-01','2026-09-30',10,2,'En curso',25)"""
            )
        )
        connection.execute(
            text(
                """INSERT INTO consumo
                (proyecto_id,recurso_id,fecha_inicio,fecha_fin,horas_consumidas,tarea,rol_id)
                VALUES (1,2,'2026-09-02','2026-09-02',3,'Diseño',1)"""
            )
        )
    return app


@pytest.fixture
def client(seeded):
    with TestClient(seeded) as client:
        yield client


def scalar(app, sql, **params):
    with app.state.engine.connect() as connection:
        return connection.execute(text(sql), params).scalar()


def mutate(client, method, path, data=None):
    token = client.get('/api/session').json()['csrf_token']
    return client.request(method, path, json=data or {}, headers={'X-CSRF-Token': token})


def post(client, path, data=None):
    return mutate(client, 'POST', path, data)


def login(client, name='admin', password='Proyecto1'):
    return post(client, '/api/login', {'recurso_nombre': name, 'password': password})


def project_data():
    return dict(
        proyecto_nombre='Proyecto editado',
        fecha_inicio='2026-09-01',
        fecha_fin='2026-09-30',
        horas_requeridas='10',
        owner_id='2',
        proyect_status='En curso',
        porcentaje_avance='25',
    )


def consumption_data():
    return dict(
        proyecto_id='1',
        recurso_id='2',
        fecha_inicio='2026-10-01',
        fecha_fin='2026-10-02',
        horas_consumidas='12',
        tarea='Implementación',
        rol_id='1',
    )


def xlsx_bytes(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
