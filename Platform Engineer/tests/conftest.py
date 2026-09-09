# ABOUTME: Shared pytest fixtures: database connections, the API test client, and seeded data.
# ABOUTME: Seeds the database once per session if it has no households.
import time

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app import config
from app.main import app
from app.store.sync_runs import SyncRunStore
from scripts import seed

SYNC_SETTLE_TIMEOUT_SECONDS = 240


def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row, autocommit=autocommit)


def wait_for_sync_status(conn, household_id: int, expected: set[str | None], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    runs = SyncRunStore()
    while runs.latest_status(conn, household_id) not in expected:
        if time.monotonic() > deadline:
            raise TimeoutError(f"sync for household {household_id} did not reach {expected}")
        time.sleep(0.2)


@pytest.fixture(scope="session")
def seeded_household_id() -> int:
    with connect(autocommit=True) as conn:
        row = conn.execute("SELECT id FROM households ORDER BY id LIMIT 1").fetchone()
        if row is None:
            with conn.transaction():
                seed.run(conn)
            row = conn.execute("SELECT id FROM households ORDER BY id LIMIT 1").fetchone()
        household_id = row["id"]
        # The worker may be mid-sync when the session starts; wait for a quiet baseline.
        wait_for_sync_status(
            conn, household_id, {None, "completed", "failed"}, SYNC_SETTLE_TIMEOUT_SECONDS
        )
    return household_id


@pytest.fixture
def db():
    with connect(autocommit=True) as conn:
        yield conn


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
