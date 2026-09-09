# ABOUTME: Behavioural tests for requesting stock updates and reading their status.
# ABOUTME: Runs against the seeded shop with no stock update in progress.
from app.store.stock_updates import StockUpdateStore


def test_status_reports_schedule_and_latest_run(client, shop_id):
    response = client.get("/api/v1/stock-update")
    assert response.status_code == 200
    body = response.json()
    assert body["interval_seconds"] > 0
    assert body["server_time"]
    assert "latest" in body and "next_run_at" in body


def test_request_is_accepted_and_recorded(client, db, shop_id):
    response = client.post("/api/v1/stock-update")
    assert response.status_code == 202, response.json()
    body = response.json()
    assert body["status"] == "requested"
    assert body["started_at"] is None
    latest = client.get("/api/v1/stock-update").json()["latest"]
    assert latest["id"] == body["id"]
    db.execute("DELETE FROM stock_updates WHERE id = %s", (body["id"],))


def test_claiming_a_requested_run_marks_it_running(client, db, shop_id):
    requested = client.post("/api/v1/stock-update").json()
    with db.transaction():
        claimed = StockUpdateStore().claim_requested(db)
    assert claimed == {"id": requested["id"], "shop_id": shop_id}
    row = db.execute("SELECT status, started_at FROM stock_updates WHERE id = %s", (requested["id"],)).fetchone()
    assert row["status"] == "running"
    assert row["started_at"] is not None
    with db.transaction():
        assert StockUpdateStore().claim_requested(db) is None
    db.execute("DELETE FROM stock_updates WHERE id = %s", (requested["id"],))
