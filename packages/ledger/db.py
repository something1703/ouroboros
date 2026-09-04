"""SQLAlchemy engine/session factory.

How we actually reach Cloud SQL (private IP via the Serverless VPC Access connector from
Cloud Run, or the Cloud SQL Auth Proxy on localhost for a developer's laptop, or the local
docker-compose postgres) is entirely determined by DB_HOST/DB_PORT — this module has no
Cloud-SQL-specific logic of its own.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from packages.common.secrets import get_secret


def _database_url() -> str:
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "ouroboros")
    user = os.environ.get("DB_USER", "app")
    password = get_secret("DB_PASSWORD")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        # pool_size/max_overflow explicit, deliberately *small* -- found live (docs/
        # DECISIONS.md #055, #060) that the demo Cloud SQL instance is db-f1-micro,
        # `max_connections=25` total, shared across every service that touches it
        # (this process, Toolbox's own separate pool, dashboard-api, ingest). A first
        # attempt raised this to pool_size=20 (30 total) to fix a burst of
        # ConnectionTimeout errors during a real CLEAR pass -- that only let *this one
        # consumer* claim more of the same small shared budget, and the timeouts
        # continued once Toolbox's concurrent connections were counted too. The actual
        # fix was lowering agents/ouroboros/clear/specialist.py's per-claim concurrency
        # (peak demand), not raising this pool (this service's share of a fixed, small
        # supply) -- kept modest here so this process alone can't starve the other
        # services sharing the same instance. Revisit if the Cloud SQL tier changes.
        _engine = create_engine(_database_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """`with session_scope() as session: ...` — commits on success, rolls back on exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
