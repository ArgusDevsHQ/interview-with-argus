# ABOUTME: Reads shop rows.
# ABOUTME: A shop is the unit that stock is counted and updated for.
from psycopg import Connection


class ShopStore:
    def get(self, conn: Connection, shop_id: int) -> dict | None:
        return conn.execute("SELECT id, name FROM shops WHERE id = %s", (shop_id,)).fetchone()

    def list_ids(self, conn: Connection) -> list[int]:
        rows = conn.execute("SELECT id FROM shops ORDER BY id").fetchall()
        return [row["id"] for row in rows]
