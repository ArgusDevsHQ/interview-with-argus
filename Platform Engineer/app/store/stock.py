# ABOUTME: Rebuilds a shop's stock levels and FIFO cost layers from its movement history
# ABOUTME: and records how each movement compares with the shelf scanner counts.
from collections import defaultdict, deque

from psycopg import Connection

from app.store.base import Store
from app.store.scanner_counts import ScannerCountStore


class StockStore(Store):
    def __init__(self) -> None:
        self.scanner_counts = ScannerCountStore()

    def rebuild(self, conn: Connection, shop_id: int) -> int:
        self._ensure_stock_authority(conn, shop_id)
        conn.execute("DELETE FROM stock_checks WHERE shop_id = %s", (shop_id,))
        conn.execute(
            "DELETE FROM cost_layers WHERE product_id IN (SELECT id FROM products WHERE shop_id = %s)",
            (shop_id,),
        )
        movements = conn.execute(
            """
            SELECT id, product_id, moved_at, kind, quantity, unit_cost_cents
            FROM stock_movements
            WHERE shop_id = %s
            ORDER BY moved_at, id
            """,
            (shop_id,),
        ).fetchall()

        on_hand: dict[int, int] = defaultdict(int)
        layers: dict[int, deque] = defaultdict(deque)
        for movement in movements:
            product_id = movement["product_id"]
            on_hand[product_id] += movement["quantity"]
            if movement["quantity"] > 0:
                layers[product_id].append(
                    [movement["id"], movement["quantity"], movement["unit_cost_cents"] or 0]
                )
            else:
                self._consume(layers[product_id], -movement["quantity"])
            scanned = self.scanner_counts.count_on(
                conn, product_id, movement["moved_at"].date()
            )
            conn.execute(
                """
                INSERT INTO stock_checks
                    (shop_id, movement_id, product_id, counted_on, ledger_quantity, scanned_quantity)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (shop_id, movement["id"], product_id, movement["moved_at"].date(), on_hand[product_id], scanned),
            )

        self._publish(conn, shop_id, on_hand, layers)
        return len(movements)

    @staticmethod
    def _consume(product_layers: deque, quantity: int) -> None:
        remaining = quantity
        while remaining > 0 and product_layers:
            layer = product_layers[0]
            taken = min(layer[1], remaining)
            layer[1] -= taken
            remaining -= taken
            if layer[1] == 0:
                product_layers.popleft()

    def _publish(self, conn: Connection, shop_id: int, on_hand: dict, layers: dict) -> None:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO cost_layers (product_id, movement_id, quantity_remaining, unit_cost_cents)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (product_id, movement_id, remaining, unit_cost)
                    for product_id, product_layers in layers.items()
                    for movement_id, remaining, unit_cost in product_layers
                ],
            )
            cur.executemany(
                """
                INSERT INTO stock_levels (product_id, on_hand, value_cents, computed_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (product_id) DO UPDATE
                SET on_hand = EXCLUDED.on_hand, value_cents = EXCLUDED.value_cents,
                    computed_at = EXCLUDED.computed_at
                """,
                [
                    (
                        product_id,
                        quantity,
                        sum(remaining * unit_cost for _, remaining, unit_cost in layers[product_id]),
                    )
                    for product_id, quantity in on_hand.items()
                ],
            )
