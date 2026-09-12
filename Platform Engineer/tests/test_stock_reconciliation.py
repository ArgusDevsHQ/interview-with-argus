# ABOUTME: Verifies why the background rebuild exists: repair derived inventory from its ledger.
# ABOUTME: Checks stock quantity, oldest-delivery-first costs, and scanner comparisons together.
from datetime import date
from unittest.mock import Mock

from app.providers.scanners import ScannerFeed, ScannerReading
from app.services.stock_update import run_stock_update


def test_rebuild_repairs_inventory_from_ledger_without_rewriting_history(db):
    # Everything belongs to a temporary shop and rolls back, including the
    # rebuild's nested transactions, so this cannot alter the seeded shop.
    with db.transaction(force_rollback=True):
        shop_id = db.execute(
            "INSERT INTO shops (name) VALUES ('Reconciliation test') RETURNING id"
        ).fetchone()["id"]
        product_id = db.execute(
            """
            INSERT INTO products (shop_id, sku, name, price_cents)
            VALUES (%s, %s, 'Test coffee', 1500) RETURNING id
            """,
            (shop_id, f"RECONCILIATION-{shop_id}"),
        ).fetchone()["id"]
        movement_ids = []
        for offset, kind, quantity, cost in (
            (0, "received", 10, 500),
            (1, "received", 5, 700),
            (2, "sold", -12, None),
        ):
            movement_ids.append(db.execute(
                """
                INSERT INTO stock_movements
                    (shop_id, product_id, moved_at, kind, quantity, unit_cost_cents)
                VALUES (%s, %s, current_date + %s * interval '1 second', %s, %s, %s)
                RETURNING id
                """,
                (shop_id, product_id, offset, kind, quantity, cost),
            ).fetchone()["id"])

        # The ledger says three bags remain from the second delivery, worth
        # 3 * 700 cents. Both saved quantity and saved cost information are wrong.
        db.execute(
            """
            INSERT INTO stock_levels (product_id, on_hand, value_cents, computed_at)
            VALUES (%s, 99, 49500, now())
            """,
            (product_id,),
        )
        db.execute(
            """
            INSERT INTO cost_layers (product_id, movement_id, quantity_remaining, unit_cost_cents)
            VALUES (%s, %s, 99, 500)
            """,
            (product_id, movement_ids[0]),
        )
        history_query = "SELECT * FROM stock_movements WHERE shop_id = %s ORDER BY id"
        history = db.execute(history_query, (shop_id,)).fetchall()
        feed = Mock(spec=ScannerFeed)
        feed.fetch_today.return_value = [ScannerReading(product_id, date.today(), 999)]

        run_stock_update(db, shop_id, feed=feed)

        assert db.execute(history_query, (shop_id,)).fetchall() == history
        assert db.execute(
            "SELECT on_hand, value_cents FROM stock_levels WHERE product_id = %s", (product_id,)
        ).fetchone() == {"on_hand": 3, "value_cents": 2100}
        assert db.execute(
            """
            SELECT movement_id, quantity_remaining, unit_cost_cents
            FROM cost_layers WHERE product_id = %s ORDER BY movement_id
            """,
            (product_id,),
        ).fetchall() == [{
            "movement_id": movement_ids[1], "quantity_remaining": 3, "unit_cost_cents": 700,
        }]
        assert db.execute(
            """
            SELECT movement_id, ledger_quantity, scanned_quantity
            FROM stock_checks WHERE shop_id = %s ORDER BY movement_id
            """,
            (shop_id,),
        ).fetchall() == [
            {"movement_id": movement_ids[0], "ledger_quantity": 10, "scanned_quantity": 999},
            {"movement_id": movement_ids[1], "ledger_quantity": 15, "scanned_quantity": 999},
            {"movement_id": movement_ids[2], "ledger_quantity": 3, "scanned_quantity": 999},
        ]
