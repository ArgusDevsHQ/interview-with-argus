# ABOUTME: Reads household rows.
# ABOUTME: Households are the unit that valuations are computed for.
from psycopg import Connection


class HouseholdStore:
    def get(self, conn: Connection, household_id: int) -> dict | None:
        return conn.execute(
            "SELECT id, name, created_at FROM households WHERE id = %s", (household_id,)
        ).fetchone()

    def list_ids(self, conn: Connection) -> list[int]:
        rows = conn.execute("SELECT id FROM households ORDER BY id").fetchall()
        return [row["id"] for row in rows]
