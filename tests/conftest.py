"""Integration test fixtures — a real Postgres, per PHASE_02.md §2.2 ("Integration tests
(local postgres in CI via service container)"). Not part of `-m live`: this is our own
infra (docker-compose locally, a service container in CI), not an external API.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_NAME", "ouroboros")
os.environ.setdefault("DB_USER", "app")
os.environ.setdefault("DB_PASSWORD", "localdev")

from packages.ledger.db import get_engine
from packages.ledger.tables import Base


@pytest.fixture(scope="session")
def engine() -> Engine:
    eng = get_engine()
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
