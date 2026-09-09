# ABOUTME: Verifies that manual holding entry keeps working while a provider sync is in progress.
# ABOUTME: Drives the sync on its own database connection and calls the API through the test client.
import threading
import time

import pytest

from app.services.sync import sync_household
from tests.conftest import connect, wait_for_sync_status


@pytest.fixture
def running_sync(seeded_household_id, db):
    sync_conn = connect()
    failures: list[Exception] = []

    def run() -> None:
        try:
            sync_household(sync_conn, seeded_household_id)
        except Exception as exc:
            failures.append(exc)

    thread = threading.Thread(target=run, name="sync", daemon=True)
    thread.start()
    wait_for_sync_status(db, seeded_household_id, {"running"}, timeout=30)
    # Give the sync a moment to get past its bookkeeping and into the recompute.
    time.sleep(2)
    yield
    sync_conn.cancel_safe()
    thread.join(timeout=30)
    sync_conn.close()


def test_create_holding_while_sync_is_running(client, seeded_household_id, running_sync):
    response = client.post(
        "/api/v1/holdings",
        json={"household_id": seeded_household_id, "symbol": "QQQ", "quantity": "2"},
    )
    assert response.status_code == 201, response.json()
