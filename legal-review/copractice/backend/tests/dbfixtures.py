"""Each test session gets a fresh throwaway database on the local Postgres
(TEST_DATABASE_ADMIN_URL, default: local socket on port 5433)."""

import os
import uuid

import psycopg
import pytest

ADMIN = os.environ.get("TEST_DATABASE_ADMIN_URL", "postgresql://postgres@/postgres?host=/var/run/postgresql&port=5433")


@pytest.fixture(scope="session")
def db_url():
    name = "cp_test_" + uuid.uuid4().hex[:8]
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{name}"')
    url = ADMIN.replace("/postgres?", f"/{name}?")
    yield url
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture(scope="session")
def conn(db_url):
    from app.db import connect, migrate

    c = connect(db_url)
    migrate(c)
    yield c
    c.close()
