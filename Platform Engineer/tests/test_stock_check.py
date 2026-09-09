# ABOUTME: Behavioural tests for the stock check that compares stock counts with the movement ledger.
# ABOUTME: Runs against the seeded shop with no stock update in progress.


def test_stock_check_passes_on_a_consistent_shop(client, shop_id):
    response = client.get("/api/v1/stock-check")
    assert response.status_code == 200
    body = response.json()
    assert body["products_checked"] > 0
    assert body["mismatches"] == []


def test_stock_check_reports_a_count_that_disagrees_with_the_ledger(client, db, featured_product_id):
    db.execute("UPDATE stock_levels SET on_hand = on_hand + 3 WHERE product_id = %s", (featured_product_id,))
    try:
        body = client.get("/api/v1/stock-check").json()
        assert len(body["mismatches"]) == 1
        mismatch = body["mismatches"][0]
        assert mismatch["product_id"] == featured_product_id
        assert mismatch["on_hand"] - mismatch["ledger"] == 3
        assert mismatch["name"]
    finally:
        db.execute("UPDATE stock_levels SET on_hand = on_hand - 3 WHERE product_id = %s", (featured_product_id,))
