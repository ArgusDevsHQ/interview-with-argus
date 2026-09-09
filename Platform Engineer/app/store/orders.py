# ABOUTME: Persists customer orders and takes the ordered quantity out of stock.
# ABOUTME: An order writes a sale movement and decrements the product's stock level.
from psycopg import Connection

from app.store.base import Store


class OutOfStock(Exception):
    pass


class OrderStore(Store):
    def insert(
        self, conn: Connection, shop_id: int, product_id: int, quantity: int, customer: str
    ) -> dict:
        self._ensure_stock_authority(conn, shop_id)
        level = conn.execute(
            "SELECT on_hand FROM stock_levels WHERE product_id = %s", (product_id,)
        ).fetchone()
        on_hand = level["on_hand"] if level else 0
        if on_hand < quantity:
            raise OutOfStock(product_id)
        order = conn.execute(
            """
            INSERT INTO orders (shop_id, product_id, quantity, customer)
            VALUES (%s, %s, %s, %s)
            RETURNING id, shop_id, product_id, quantity, customer, created_at
            """,
            (shop_id, product_id, quantity, customer),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO stock_movements (shop_id, product_id, moved_at, kind, quantity)
            VALUES (%s, %s, now(), 'sold', %s)
            """,
            (shop_id, product_id, -quantity),
        )
        updated = conn.execute(
            """
            UPDATE stock_levels SET on_hand = on_hand - %s
            WHERE product_id = %s
            RETURNING on_hand
            """,
            (quantity, product_id),
        ).fetchone()
        return {**order, "on_hand": updated["on_hand"]}
