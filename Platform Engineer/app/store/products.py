# ABOUTME: Reads products and their current stock level.
# ABOUTME: The storefront shows featured products only; the shop carries many more.
from psycopg import Connection


class ProductStore:
    def get(self, conn: Connection, product_id: int) -> dict | None:
        return conn.execute(
            """
            SELECT p.id, p.shop_id, p.sku, p.name, p.notes, p.price_cents, p.featured,
                   COALESCE(l.on_hand, 0) AS on_hand
            FROM products p
            LEFT JOIN stock_levels l ON l.product_id = p.id
            WHERE p.id = %s
            """,
            (product_id,),
        ).fetchone()

    def list_featured(self, conn: Connection, shop_id: int) -> list[dict]:
        return conn.execute(
            """
            SELECT p.id, p.sku, p.name, p.notes, p.price_cents, COALESCE(l.on_hand, 0) AS on_hand
            FROM products p
            LEFT JOIN stock_levels l ON l.product_id = p.id
            WHERE p.shop_id = %s AND p.featured
            ORDER BY p.id
            """,
            (shop_id,),
        ).fetchall()

    def list_ids(self, conn: Connection, shop_id: int) -> list[int]:
        rows = conn.execute("SELECT id FROM products WHERE shop_id = %s ORDER BY id", (shop_id,)).fetchall()
        return [row["id"] for row in rows]
