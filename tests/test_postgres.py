"""Real PostgreSQL migration and privilege checks, enabled in GitHub Actions.

Local runs without TEST_DATABASE_URL skip these checks. SQLite fixtures never
stand in for the migration or database privilege checks.
"""

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from agent_api.config import Settings
from agent_api.database import Database
from agent_api.main import create_app
from agent_api.migrate import migrate

from conftest import API_KEY


pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def migrated_postgres():
    owner_url = os.environ.get("TEST_DATABASE_URL")
    if not owner_url:
        pytest.skip("TEST_DATABASE_URL is not set; PostgreSQL checks run in CI")
    read_password = os.environ.get("READ_DB_PASSWORD", "demo-reader-password-2026")
    environment = {**os.environ, "DATABASE_URL": owner_url, "READ_DB_PASSWORD": read_password}
    for _ in range(2):
        completed = subprocess.run(
            [sys.executable, "-m", "agent_api.migrate", "--demo-bootstrap"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
    reader_url = os.environ.get("TEST_READ_DATABASE_URL")
    if not reader_url:
        reader_url = make_url(owner_url).set(username="agent_reader", password=read_password).render_as_string(hide_password=False)
    engine = create_engine(reader_url)
    yield owner_url, reader_url, engine
    engine.dispose()


def test_postgres_migrations_are_idempotent_and_seeded(migrated_postgres):
    _, _, reader_engine = migrated_postgres
    with reader_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM customers")).scalar_one() == 2
        assert connection.execute(text("SELECT count(*) FROM orders WHERE customer_id = :id"), {"id": "cus_001"}).scalar_one() == 3
        assert connection.execute(text("SELECT count(*) FROM invoices WHERE customer_id = :id"), {"id": "cus_001"}).scalar_one() == 3


def test_postgres_reader_defaults_to_read_only_transactions(migrated_postgres):
    _, _, reader_engine = migrated_postgres
    with reader_engine.connect() as connection:
        assert connection.execute(text("SHOW default_transaction_read_only")).scalar_one() == "on"


def test_bootstrap_removes_accidental_existing_write_grant(migrated_postgres):
    owner_url, _, reader_engine = migrated_postgres
    owner_engine = create_engine(owner_url)
    try:
        with owner_engine.begin() as connection:
            connection.execute(text("GRANT INSERT ON customers TO agent_reader"))
            connection.execute(text("GRANT CREATE ON SCHEMA public TO agent_reader"))
        with reader_engine.connect() as connection:
            assert connection.execute(
                text("SELECT has_table_privilege(current_user, 'customers', 'INSERT')")
            ).scalar_one() is True

        migrate(
            database_url=owner_url,
            demo_bootstrap=True,
            read_password=os.environ.get("READ_DB_PASSWORD", "demo-reader-password-2026"),
        )

        with reader_engine.connect() as connection:
            privileges = connection.execute(text("""SELECT
                has_table_privilege(current_user, 'customers', 'INSERT') AS can_insert,
                has_table_privilege(current_user, 'customers', 'SELECT') AS can_select,
                has_schema_privilege(current_user, 'public', 'CREATE') AS can_create
            """)).mappings().one()
            assert privileges["can_insert"] is False
            assert privileges["can_select"] is True
            assert privileges["can_create"] is False
            connection.rollback()
            connection.execute(text("SET TRANSACTION READ WRITE"))
            with pytest.raises(DBAPIError) as error:
                connection.execute(text(
                    "INSERT INTO customers (id, name, tier) VALUES ('cus_999', 'Forbidden customer', 'standard')"
                ))
            sqlstate = getattr(error.value.orig, "sqlstate", None) or getattr(error.value.orig, "pgcode", None)
            assert sqlstate == "42501"
            connection.rollback()
    finally:
        # Leave the shared disposable test database restricted even on failure.
        with owner_engine.begin() as connection:
            connection.execute(text("REVOKE INSERT ON customers FROM agent_reader"))
            connection.execute(text("REVOKE CREATE ON SCHEMA public FROM agent_reader"))
        owner_engine.dispose()


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO customers (id, name, tier) VALUES ('cus_999', 'Forbidden customer', 'standard')",
        "UPDATE orders SET status = 'cancelled' WHERE id = 'ord_001'",
        "DELETE FROM invoices WHERE id = 'inv_001'",
    ],
)
def test_postgres_reader_cannot_write(migrated_postgres, statement):
    _, _, reader_engine = migrated_postgres
    with reader_engine.connect() as connection:
        # Transaction defaults are user-changeable. Even with that guard disabled,
        # the account must still lack write privileges on the underlying tables.
        connection.execute(text("SET TRANSACTION READ WRITE"))
        with pytest.raises(DBAPIError) as error:
            connection.execute(text(statement))
        sqlstate = getattr(error.value.orig, "sqlstate", None) or getattr(error.value.orig, "pgcode", None)
        assert sqlstate == "42501", "Expected PostgreSQL insufficient_privilege"
        connection.rollback()


def test_api_runs_against_postgres_read_only_account(migrated_postgres):
    _, reader_url, _ = migrated_postgres
    database = Database(reader_url)
    settings = Settings(database_url=str(reader_url), api_key=API_KEY, allowed_customer_ids=("cus_001",))
    try:
        with TestClient(create_app(settings=settings, database=database)) as client:
            assert client.get("/ready").status_code == 200
            response = client.get("/v1/customers/cus_001/orders", headers={"X-API-Key": API_KEY})
            assert response.status_code == 200
            assert response.json()["count"] == 3
    finally:
        database.engine.dispose()
