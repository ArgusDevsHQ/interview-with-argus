# ABOUTME: Base class for store objects that write shop-scoped stock data.
# ABOUTME: Holds the helpers shared by the orders and stock stores.
from psycopg import Connection


class Store:
    def _ensure_stock_authority(self, conn: Connection, shop_id: int) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"shop:{shop_id}",),
        )
