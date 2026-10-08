import os
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.drivername in ('postgres', 'postgresql'):
        # Neon/Vercel inject plain `postgresql://` URLs; the app uses psycopg 3.
        parsed = parsed.set(drivername='postgresql+psycopg')
    if os.environ.get('VERCEL'):
        # Serverless: every function instance is short-lived, so pooling is left to Neon's pgbouncer
        # (transaction mode, so psycopg must not keep server-side prepared statements).
        return create_engine(parsed, poolclass=NullPool, connect_args={'prepare_threshold': None})
    return create_engine(parsed, pool_pre_ping=True)


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """One SQLAlchemy session per request, bound to the app's engine."""
    with request.app.state.sessionmaker() as db:
        yield db
