# ABOUTME: Verifies that customers can keep placing orders while a stock update is in progress.
# ABOUTME: Drives the update on its own database connection and orders through the test client.
import threading
import time

import pytest

from app.services.stock_update import run_stock_update
from tests.conftest import connect, wait_for_update_status


@pytest.fixture
def running_stock_update(shop_id, db):
    update_conn = connect()
    failures: list[Exception] = []

    def run() -> None:
        try:
            run_stock_update(update_conn, shop_id)
        except Exception as exc:
            failures.append(exc)

    thread = threading.Thread(target=run, name="stock-update", daemon=True)
    thread.start()
    wait_for_update_status(db, shop_id, {"running"}, give_up_after=30)
    # Give the update a moment to get past its bookkeeping and into the replay.
    time.sleep(2)
    yield
    update_conn.cancel_safe()
    thread.join(30)
    update_conn.close()


def test_place_order_while_stock_update_is_running(client, featured_product_id, running_stock_update):
    response = client.post("/api/v1/orders", json={"product_id": featured_product_id, "quantity": 1})
    assert response.status_code == 201, response.json()
