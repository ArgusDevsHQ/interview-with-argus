# ABOUTME: Verifies that customers can keep placing orders while a stock update is in progress.
# ABOUTME: Drives the update on its own database connection and orders through the test client.
import threading
import time

from psycopg.errors import QueryCanceled

from app.services.stock_update import run_stock_update
from app.store.scanner_counts import ScannerCountStore
from tests.conftest import connect


def test_place_order_while_stock_update_is_running(client, featured_product_id, shop_id, db, monkeypatch):
    update_conn = connect()
    replay_entered = threading.Event()
    resume_replay = threading.Event()
    order_finished = threading.Event()
    update_failures: list[Exception] = []
    order_failures: list[Exception] = []
    responses = []
    count_on = ScannerCountStore.count_on

    def coordinated_count_on(self, conn, product_id, counted_on):
        # Pause once inside the replay so even an indexed rebuild cannot finish
        # before the order starts. This is synchronization, not a slow workload:
        # release it as soon as the order completes or reaches the worker's lock.
        if conn is update_conn and not replay_entered.is_set():
            replay_entered.set()
            if not resume_replay.wait(30):
                raise TimeoutError("the test never released the replay")
        return count_on(self, conn, product_id, counted_on)

    monkeypatch.setattr(ScannerCountStore, "count_on", coordinated_count_on)

    def run() -> None:
        try:
            run_stock_update(update_conn, shop_id)
        except Exception as exc:
            update_failures.append(exc)

    def order() -> None:
        try:
            responses.append(client.post(
                "/api/v1/orders", json={"product_id": featured_product_id, "quantity": 1}
            ))
        except Exception as exc:
            order_failures.append(exc)
        finally:
            order_finished.set()

    thread = threading.Thread(target=run, name="stock-update", daemon=True)
    order_thread = threading.Thread(target=order, name="customer-order", daemon=True)
    thread.start()
    try:
        assert replay_entered.wait(30), f"the rebuild never reached its replay: {update_failures}"
        order_thread.start()
        deadline = time.monotonic() + 10
        while not order_finished.wait(0.01):
            blocked = db.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_stat_activity
                    WHERE %s = ANY(pg_blocking_pids(pid))
                ) AS blocked
                """,
                (update_conn.info.backend_pid,),
            ).fetchone()["blocked"]
            if blocked:
                break
            assert time.monotonic() < deadline, "the order never reached the rebuild"
        resume_replay.set()
        assert order_finished.wait(15), "the order did not finish after the replay resumed"
        assert not order_failures, order_failures
        response = responses[0]
        assert response.status_code == 201, response.json()
    finally:
        resume_replay.set()
        # Availability is the assertion here. Avoid waiting for the rest of a
        # slow rebuild after the order finishes, but surface unexpected failures.
        if thread.is_alive():
            update_conn.cancel_safe()
        thread.join(30)
        if order_thread.ident is not None:
            order_thread.join(30)
        update_conn.close()

    assert not thread.is_alive(), "the rebuild did not stop"
    assert not order_thread.is_alive(), "the order did not stop"
    assert not [exc for exc in update_failures if not isinstance(exc, QueryCanceled)], update_failures
