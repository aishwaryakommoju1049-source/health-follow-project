"""Shared fixtures.

Three groups:

*   ``stub_llm`` — replaces every model in the system. Applied automatically
    to every test, so an unstubbed model call fails loudly rather than
    reaching the network.
*   Database fixtures — a real Postgres, one transaction per test, rolled
    back afterwards so tests cannot see each other's data.
*   ``client`` — FastAPI test client.

See docs/TESTING_STRATEGY.md.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import NoSuchModuleError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.main import app
from tests.support.stub_llm import StubChatModel

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://mediagent:dev@localhost:5433/mediagent_test",
)


# ---------------------------------------------------------------------------
# Model stubbing
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch: pytest.MonkeyPatch) -> StubChatModel:
    """Replace every chat model with a scripted stub.

    ``autouse`` is deliberate: a test that reaches a real provider by accident
    should fail, not quietly spend money. ``app.core.llm.get_model`` raises
    NotImplementedError until providers are wired, so this fixture is also
    what makes agent tests possible at all.
    """
    stub = StubChatModel()

    # Patch the provider builder, NOT get_model. Nodes typically write
    # `from app.core.llm import get_model`, which binds the original function
    # into their own module — a patch on get_model would never reach them.
    # _build is looked up as a module global at call time, so this intercepts
    # every caller regardless of import style.
    monkeypatch.setattr(
        "app.core.llm._build",
        lambda provider, model, tier: stub._bind(tier),
    )
    return stub


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Session-wide engine against the *test* database.

    If Postgres is unreachable, behaviour differs by environment on purpose:
    locally it skips with a clear message (docker probably is not running);
    in CI it fails, because the service container is guaranteed and a silent
    skip there would hide a broken suite.
    """
    try:
        eng = create_engine(TEST_DATABASE_URL, future=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (OperationalError, ImportError, NoSuchModuleError) as exc:
        # ImportError: the psycopg driver is not installed.
        # OperationalError: the driver is fine but nothing is listening.
        message = (
            f"Test database unavailable at {TEST_DATABASE_URL}.\n"
            f"  pip install -r requirements-dev.txt\n"
            f"  docker compose up -d db-test\n"
            f"Original error: {exc}"
        )
        if settings.is_ci:
            pytest.fail(message, pytrace=False)
        pytest.skip(message, allow_module_level=True)

    # Tables are created from the SQLAlchemy metadata rather than by running
    # migrations, because it is much faster. Once Alembic migrations exist,
    # add a test asserting the two do not drift — see TESTING_STRATEGY.md §4.
    from app.db.base import Base

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    conn = engine.connect()
    transaction = conn.begin()
    try:
        yield conn
    finally:
        transaction.rollback()  # nothing a test writes ever persists
        conn.close()


@pytest.fixture
def db(connection: Connection) -> Iterator[Session]:
    """A session bound to a transaction that is rolled back after the test."""
    factory = sessionmaker(bind=connection, expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
