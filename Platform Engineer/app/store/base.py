# ABOUTME: Base class for store objects that write household-scoped data.
# ABOUTME: Holds the helpers shared by the holdings and valuation stores.
from psycopg import Connection


class Store:
    def _ensure_valuation_authority(self, conn: Connection, household_id: int) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"household:{household_id}",),
        )
