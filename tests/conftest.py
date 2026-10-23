"""Portable SQLite fixtures for API contracts; PostgreSQL is tested separately."""

import pytest
from fastapi.testclient import TestClient

from agent_api.config import Settings
from agent_api.database import Database
from agent_api.main import create_app


API_KEY = "test-customer-key-0123456789abcdef"


@pytest.fixture
def database(tmp_path):
    db = Database(f"sqlite:///{(tmp_path / 'customer-test.db').as_posix()}")
    db.prepare_sqlite_demo()
    yield db
    db.engine.dispose()


@pytest.fixture
def settings(database):
    return Settings(
        database_url=str(database.engine.url),
        api_key=API_KEY,
        allowed_customer_ids=("cus_001",),
        rate_limit=100,
        rate_window_seconds=60.0,
    )


@pytest.fixture
def app(settings, database):
    return create_app(settings=settings, database=database)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {"X-API-Key": API_KEY}
