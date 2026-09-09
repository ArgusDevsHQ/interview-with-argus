# ABOUTME: Shared pytest fixtures: database connections, the API test client, and seeded data.
# ABOUTME: Seeds the database once per session if it has no shop.
import time

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app import config
from app.main import app
from app.store.stock_updates import StockUpdateStore
from scripts import seed

UPDATE_SETTLE_TIMEOUT_SECONDS = 240


def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row, autocommit=autocommit)


def wait_for_update_status(conn, shop_id: int, expected: set[str | None], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    runs = StockUpdateStore()
    while runs.latest_status(conn, shop_id) not in expected:
        if time.monotonic() > deadline:
            raise TimeoutError(f"stock update for shop {shop_id} did not reach {expected}")
        time.sleep(0.2)


@pytest.fixture(scope="session")
def shop_id() -> int:
    with connect(autocommit=True) as conn:
        row = conn.execute("SELECT id FROM shops ORDER BY id LIMIT 1").fetchone()
        if row is None:
            with conn.transaction():
                seed.run(conn)
            row = conn.execute("SELECT id FROM shops ORDER BY id LIMIT 1").fetchone()
        # The worker may be mid-update when the session starts; wait for a quiet baseline.
        wait_for_update_status(conn, row["id"], {None, "completed", "failed"}, UPDATE_SETTLE_TIMEOUT_SECONDS)
        return row["id"]


@pytest.fixture(scope="session")
def featured_product_id(shop_id) -> int:
    with connect(autocommit=True) as conn:
        row = conn.execute(
            "SELECT id FROM products WHERE shop_id = %s AND featured ORDER BY id LIMIT 1", (shop_id,)
        ).fetchone()
        return row["id"]


@pytest.fixture
def db():
    with connect(autocommit=True) as conn:
        yield conn


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
