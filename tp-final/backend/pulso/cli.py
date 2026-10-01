"""Command line tasks.

python -m pulso.cli init-db               # migrate + seed admin/Proyecto1 on an empty install
python -m pulso.cli import-sqlite FILE    # copy the Flask-era SQLite database into Postgres
"""

import argparse
import os
import sqlite3
from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import Settings
from .models import Consumo, Proyecto, Recurso, Rol
from .security import hash_password

ALEMBIC_INI = Path(__file__).resolve().parent.parent / 'alembic.ini'
INITIAL_ADMIN = ('admin', 'Proyecto1')

# The Flask-era SQLite database stored these in lowercase; the current schema capitalizes them.
LEGACY_STATUSES = {
    'pendiente': 'Pendiente', 'en curso': 'En curso', 'pausado': 'Pausado', 'finalizado': 'Finalizado',
}  # fmt: skip


def database_url() -> str:
    return os.environ.get('DATABASE_URL') or Settings.model_fields['database_url'].default


def migrate(url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.attributes['database_url'] = url
    config.attributes['configure_logger'] = False
    command.upgrade(config, 'head')


def seed(engine: Engine) -> bool:
    """Create the initial admin only on an empty installation; never touches existing accounts."""
    with Session(engine) as db:
        if db.scalar(select(func.count()).select_from(Recurso)):
            return False
        name, password = INITIAL_ADMIN
        db.add(Recurso(recurso_nombre=name, password=hash_password(password), es_admin=True))
        db.commit()
        return True


def init_db(url: str) -> bool:
    migrate(url)
    engine = create_engine(url)
    try:
        return seed(engine)
    finally:
        engine.dispose()


TABLES = [  # parent tables first; (model, id column, converters)
    (Recurso, 'recurso_id', {'es_admin': bool, 'debe_cambiar_password': bool}),
    (Rol, 'rol_id', {}),
    (
        Proyecto,
        'proyecto_id',
        {
            'fecha_inicio': date.fromisoformat,
            'fecha_fin': date.fromisoformat,
            'proyect_status': lambda v: LEGACY_STATUSES.get(v, v),
        },
    ),
    (Consumo, 'consumo_id', {'fecha_inicio': date.fromisoformat, 'fecha_fin': date.fromisoformat}),
]


def import_sqlite(path: str, url: str) -> dict[str, int]:
    """Copy every row keeping IDs (and legacy password hashes, upgraded at next login)."""
    migrate(url)
    source = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    engine = create_engine(url)
    counts = {}
    try:
        with Session(engine) as db, db.begin():
            if any(db.scalar(select(func.count()).select_from(model)) for model, _, _ in TABLES):
                raise SystemExit('La base destino ya tiene datos; importá sobre una instalación vacía.')
            for model, key, converters in TABLES:
                table = model.__tablename__
                rows = source.execute(f'SELECT * FROM {table} ORDER BY {key}').fetchall()
                for row in rows:
                    values = {name: converters.get(name, lambda v: v)(row[name]) for name in row.keys()}
                    db.add(model(**values))
                db.flush()
                db.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', '{key}'), "
                        f'COALESCE((SELECT MAX({key}) FROM {table}), 0) + 1, false)'
                    )
                )
                counts[table] = len(rows)
    finally:
        source.close()
        engine.dispose()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(prog='python -m pulso.cli')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init-db', help='Aplica migraciones y crea admin/Proyecto1 si no hay usuarios.')
    importer = commands.add_parser('import-sqlite', help='Importa la base SQLite de la versión Flask.')
    importer.add_argument('path')
    args = parser.parse_args()
    url = database_url()
    if args.command == 'init-db':
        created = init_db(url)
        print('Base inicializada.' + (' Usuario inicial: admin / Proyecto1.' if created else ''))
    else:
        for table, count in import_sqlite(args.path, url).items():
            print(f'{table}: {count} filas importadas')


if __name__ == '__main__':
    main()
